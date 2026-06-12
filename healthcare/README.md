# healthcare: Clinical Decision Support Agent Demo

End-to-end demo of a hospital AI agent processing patient records through a cMCP Runtime with Cedar policy enforcement and signed TRACE Trust Records for healthcare regulatory compliance (EU AI Act Art. 14, HIPAA).

---

## What the demo shows

**1. EU AI Act Article 14 - human oversight for high-risk AI**
The Cedar policy blocks any treatment plan write where `patient_risk_category == "high"`. The deny response carries the policy's `@annotation` metadata as structured advice (`regulation: eu-ai-act-art-14`, `reviewer_role: attending-physician`), and the audit chain records the deny as machine-readable Art. 14 evidence.

**2. HIPAA PHI protection at the tool boundary**
All three tools are classified `compliance_domain: hipaa_phi` in the attested catalog. A Cedar rule forbids PHI tools when no attestation evidence is present, enforcing "PHI only flows through attested runtimes" at the policy layer.

**3. Cryptographic proof of the tool call sequence**
Every call is recorded in a hash-chained audit log persisted to SQLite. Closing the session seals the chain into a signed `RuntimeClaim` (the TRACE Trust Record): which tools ran, in what order, what was denied - verifiable without trusting the agent process.

**4. Two demo paths**
Run without flags for the happy path (all three calls allowed). Run with `--trigger-hitl` to see the Art. 14 block fire with the advice payload.

---

## Architecture

```
  +------------------------------------------------------------------+
  |              Clinical Decision Support Agent (LLM)               |
  |   agent/clinical_decision_agent.py -- JSON-RPC 2.0 over HTTP     |
  +-------------------------------+----------------------------------+
                                  |  tools/call (MCP)
                                  v
  +------------------------------------------------------------------+
  |                   cMCP Runtime  :8443                            |
  |                                                                  |
  |  +---------------+  +------------------+  +------------------+  |
  |  | Cedar engine  |  | Catalog checker  |  | Audit chain +    |  |
  |  | allow.cedar   |  | catalog.json     |  | TRACE signer     |  |
  |  +---------------+  +------------------+  +------------------+  |
  +-------------------------------+----------------------------------+
                                  |  proxied tool call
                                  v
  +------------------------------------------------------------------+
  |          Mock Hospital EHR MCP Server  :8080                     |
  |   server/mock_mcp_server.py                                       |
  |   ehr.patient_record_lookup                                       |
  |   ehr.clinical_decision_support                                   |
  |   ehr.treatment_plan_writer                                       |
  +------------------------------------------------------------------+
```

---

## Run it

```bash
git clone https://github.com/agentrust-io/examples.git
cd examples
pip install cmcp-runtime httpx
```

**Terminal 1 - mock EHR server:**

```bash
cd healthcare
python server/mock_mcp_server.py
```

**Terminal 2 - runtime** (run from inside `healthcare/` - config paths resolve relative to the working directory):

```bash
cd healthcare
CMCP_DEV_MODE=1 cmcp start --config cmcp-config.yaml
```

**Terminal 3 - happy path:**

```bash
cd examples
python healthcare/agent/clinical_decision_agent.py
```

Expected output:

```
Patient: P-2024-008471  |  Risk category: standard

[1/3] Calling ehr.patient_record_lookup ...
      -> decision: allow
[2/3] Calling ehr.clinical_decision_support ...
      -> decision: allow
[3/3] Calling ehr.treatment_plan_writer ...
      -> decision: allow

Closing session <id> and fetching the signed TRACE Trust Record ...

=== TRACE Trust Record (signed RuntimeClaim) ===
{ "cmcp_version": "1.0", "trace": {...}, "gateway": {...}, "signature": "..." }
```

**HITL path:**

```bash
python healthcare/agent/clinical_decision_agent.py --trigger-hitl
```

```
[3/3] Calling ehr.treatment_plan_writer ...
      -> decision: deny (POLICY_DENY)
         advice from policy:
           id: hitl-high-risk
           reason: human-review-required
           regulation: eu-ai-act-art-14
           reviewer_role: attending-physician

  The treatment plan was NOT written to the EHR.
  An attending physician must review and approve before the plan takes effect.
```

---

## The Cedar policy

`policy/allow.cedar` has no catch-all permit: each EHR tool is explicitly permitted only for the `clinical-decision-support` workflow (declared by the agent via `_cmcp.workflow_id`), and anything else - wrong workflow, missing workflow, unlisted action - is denied by Cedar's default-deny:

```cedar
permit (
  principal,
  action == Action::"Ehr.patientRecordLookup",
  resource
) when {
  context has workflow_id &&
  context.workflow_id == "clinical-decision-support"
};
```

On top of the workflow-scoped permits sit two forbid rules. Annotations on a `forbid` are returned to the caller as structured advice when that rule causes a deny:

```cedar
@id("hitl-high-risk")
@reason("human-review-required")
@regulation("eu-ai-act-art-14")
@reviewer_role("attending-physician")
forbid (
  principal,
  action == Action::"Ehr.treatmentPlanWriter",
  resource
) when {
  context.arguments has patient_risk_category &&
  context.arguments.patient_risk_category == "high"
};
```

Action names follow the cMCP convention: `ehr.treatment_plan_writer` becomes `Action::"Ehr.treatmentPlanWriter"` (PascalCase per underscore segment). Tool arguments are available under `context.arguments`.

---

## The TRACE Trust Record

See `trace-output/example-trust-record.json` - captured from a real run of this demo. Key fields:

| Field | Meaning |
|---|---|
| `trace.policy.bundle_hash` / `version` | Exactly which Cedar bundle was enforced (`clinical-hipaa-v2.1`) |
| `trace.data_class` | Highest sensitivity touched in the session (`confidential`) |
| `trace.tool_transcript.hash` | Hash of the audit chain tip covering all calls |
| `trace.cnf.jwk` | The runtime's Ed25519 signing key (verifies `signature`) |
| `gateway.call_summary` | Allowed/denied counts, tools invoked, compliance domains touched |
| `gateway.audit_chain` | Root, tip, and length of the hash-chained audit log |
| `signature` | Ed25519 signature over the canonical claim |

Export the full audit chain for a closed session:

```bash
curl "http://localhost:8443/audit/export?session_id=<id>" | python3 -m json.tool
```

---

## Regulatory field mapping

| TRACE field | EU AI Act | HIPAA |
|---|---|---|
| `trace.policy.bundle_hash` | Art. 9 - risk management system version | 45 CFR 164.312 - access controls |
| `gateway.call_summary.tool_calls_denied` | Art. 14 - human oversight record | 45 CFR 164.308(a)(1)(ii)(D) - activity review |
| `trace.data_class` | Art. 10 - data governance | 45 CFR 164.502 - minimum necessary |
| `trace.runtime` + `signature` | Art. 12 - tamper-evident logging | 45 CFR 164.312(c) - integrity |
| `trace.subject` | Art. 12 - traceability to specific run | 45 CFR 164.308(a)(5) - access monitoring |

---

## Extending this example

- **Real EHR server:** point `server.url` in `catalog.json` at your MCP server.
- **Hardware attestation:** drop `CMCP_DEV_MODE=1` on a VM with TPM 2.0 / SEV-SNP; `trace.runtime` then carries real measurements.
- **Production hardening:** set `CMCP_BEARER_TOKEN`, `CMCP_POLICY_HASH`, and `CMCP_CATALOG_HASH` (the runtime refuses to start without them outside dev mode).

---

## License

Apache 2.0. See [LICENSE](../LICENSE) in the repo root.
