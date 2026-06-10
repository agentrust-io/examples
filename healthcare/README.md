# healthcare: Clinical Decision Support Agent Demo

End-to-end demo of a hospital AI agent processing patient records through a cMCP Runtime with Cedar policy enforcement and TRACE Trust Records for healthcare regulatory compliance (EU AI Act Art. 14, HIPAA).

---

## What the demo shows

**1. EU AI Act Article 14: human oversight for high-risk AI**
Article 14 requires that high-risk AI systems in healthcare allow human supervisors to intervene. The Cedar Rule 2 in `policy/allow.cedar` operationalises this: any treatment plan write where `patient_risk_category == "high"` is blocked until an attending physician approves. The TRACE Trust Record records the advisory deny so the block is auditable.

**2. HIPAA PHI protection at the tool boundary**
All three tools are classified `compliance_domain: hipaa_phi` and `sensitivity_level: confidential` in the catalog. Cedar Rule 3 prevents any session that has been downgraded to `public` sensitivity from calling any tool in the `hipaa_phi` domain, enforcing the minimum-necessary principle at runtime rather than in application code.

**3. Cryptographic proof of tool call sequence**
The cMCP Runtime records every EHR tool call in a signed, hash-chained audit log. The TRACE Trust Record seals the entire session (which tools ran, in what order, whether a HITL block fired) into a JWT signed by the runtime's attestation key. A compliance officer or regulator can verify the record without trusting the agent process.

**4. Two demo paths: standard and HITL**
Run without flags to see the happy path (all three calls allowed). Run with `--trigger-hitl` to see the EU AI Act Art. 14 block fire on the treatment plan write.

---

## Architecture

```
  +------------------------------------------------------------------+
  |              Clinical Decision Support Agent (LLM)               |
  |   clinical_decision_agent.py -- JSON-RPC 2.0 over HTTP           |
  +-------------------------------+----------------------------------+
                                  |  tools/call (MCP)
                                  v
  +------------------------------------------------------------------+
  |                   cMCP Runtime  :8443                            |
  |                                                                  |
  |  +---------------+  +------------------+  +------------------+  |
  |  | Cedar engine  |  | Catalog checker  |  | TRACE recorder   |  |
  |  | allow.cedar   |  | catalog.json     |  | /trace endpoint  |  |
  |  +---------------+  +------------------+  +------------------+  |
  +-------------------------------+----------------------------------+
                                  |  proxied tool call
                                  v
  +------------------------------------------------------------------+
  |              Hospital EHR MCP Server  :8080                      |
  |   ehr.patient_record_lookup                                       |
  |   ehr.clinical_decision_support                                   |
  |   ehr.treatment_plan_writer                                       |
  +------------------------------------------------------------------+
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| pip | any recent | `pip --version` |
| httpx | 0.27+ | installed by `pip install cmcp-runtime` |
| cmcp-runtime | latest | `pip install cmcp-runtime` |

No hardware TEE or TPM required for this demo. The runtime runs in `CMCP_DEV_MODE=1`.

---

## Step 1 - Clone the examples repo

```bash
git clone https://github.com/agentrust-io/examples.git
cd examples
```

---

## Step 2 - Install dependencies

```bash
pip install cmcp-runtime httpx
```

---

## Step 3 - Review the files

```
healthcare/
  cmcp-config.yaml              Runtime configuration
  catalog.json                  Three-tool EHR catalog
  policy/
    manifest.json               Policy bundle metadata
    allow.cedar                 Four Cedar rules (including HITL rule)
    schema.cedarschema          Cedar schema
  agent/
    clinical_decision_agent.py  Demo agent (run this)
  trace-output/
    example-trust-record.json   Reference TRACE output (happy path)
```

---

## Step 4 - Understand the Cedar policy

`policy/allow.cedar` contains four rules:

**Rule 1 - Workflow permit**

```cedar
permit (
  principal,
  action == Action::"tool_call",
  resource
) when {
  context.workflow_id == "clinical-decision-support"
};
```

Only the `clinical-decision-support` workflow may call the three EHR tools.

**Rule 2 - EU AI Act Art. 14 HITL block**

```cedar
forbid (
  principal,
  action == Action::"tool_call",
  resource == Tool::"ehr.treatment_plan_writer"
) when {
  context.patient_risk_category == "high"
} advice {
  "reason": "human-review-required",
  "regulation": "eu-ai-act-art-14",
  "reviewer_role": "attending-physician"
};
```

Any treatment plan write where `patient_risk_category == "high"` is blocked with an advisory deny. The advice payload is returned to the caller and recorded in the TRACE Trust Record.

**Rule 3 - HIPAA PHI session protection**

```cedar
forbid (
  principal,
  action == Action::"tool_call",
  resource
) when {
  context.session_max_sensitivity == "public" &&
  resource.compliance_domain == "hipaa_phi"
};
```

Prevents accidental PHI access if session sensitivity is downgraded.

**Rule 4 - Catch-all permit**

```cedar
permit (principal, action, resource);
```

---

## Step 5 - Start the runtime

```bash
CMCP_DEV_MODE=1 cmcp start --config healthcare/cmcp-config.yaml
```

Run from the root of the examples repo. Expected startup output:

```
[cmcp] policy bundle loaded: clinical-hipaa-v2.1
[cmcp] catalog loaded: 3 tools
[cmcp]   ehr.patient_record_lookup     (confidential)
[cmcp]   ehr.clinical_decision_support (confidential)
[cmcp]   ehr.treatment_plan_writer     (confidential)
[cmcp] attestation: dev-mode (CMCP_DEV_MODE=1)
[cmcp] enforcement: enforcing
[cmcp] listening on 0.0.0.0:8443
```

Leave this terminal open.

---

## Step 6 - Run the happy path (no HITL)

In a second terminal:

```bash
python healthcare/agent/clinical_decision_agent.py
```

Expected output:

```
Connecting to cMCP gateway at http://localhost:8443
Patient: P-2024-008471  |  Risk category: standard

[1/3] Calling ehr.patient_record_lookup ...
      -> decision: allow
[2/3] Calling ehr.clinical_decision_support ...
      -> decision: allow
[3/3] Calling ehr.treatment_plan_writer ...
      -> decision: allow

Fetching TRACE Trust Record from gateway ...

=== TRACE Trust Record ===
{
  "eat_profile": "tag:agentrust.io,2026:trace-v0.1",
  ...
}

All tool calls completed. TRACE Trust Record generated.
```

---

## Step 7 - Run the HITL path

```bash
python healthcare/agent/clinical_decision_agent.py --trigger-hitl
```

Expected output:

```
Connecting to cMCP gateway at http://localhost:8443
Patient: P-2024-008471  |  Risk category: high
Mode: --trigger-hitl enabled -- treatment plan write will require HITL approval

[1/3] Calling ehr.patient_record_lookup ...
      -> decision: allow
[2/3] Calling ehr.clinical_decision_support ...
      -> decision: allow
[3/3] Calling ehr.treatment_plan_writer ...
      -> decision: advisory_deny

  HITL advisory payload:
    reason:        human-review-required
    regulation:    eu-ai-act-art-14
    reviewer_role: attending-physician

  The treatment plan was NOT written to the EHR.
  An attending physician must review and approve before the plan takes effect.
  The TRACE Trust Record records this as an advisory_deny for EU AI Act audit purposes.
```

The TRACE Trust Record for the HITL path records `"decision": "advisory_deny"` for the treatment plan write. This entry is the machine-readable evidence that the human oversight requirement was applied.

---

## Step 8 - Verify with cmcp-verify

```bash
curl -s http://localhost:8443/trace > trace.json
cmcp-verify trace.json
```

Expected output:

```
[cmcp-verify] signature: valid
[cmcp-verify] attestation: dev-mode (not hardware-backed)
[cmcp-verify] policy version: clinical-hipaa-v2.1
[cmcp-verify] tool transcript: 3 calls (2 allowed, 1 advisory_deny)
[cmcp-verify] data_class: confidential (session maximum)
[cmcp-verify] RESULT: PASS (dev-mode)
```

---

## Regulatory field mapping

| TRACE field | EU AI Act | HIPAA |
|---|---|---|
| `policy.bundle_hash` | Art. 9: risk management system version | 45 CFR 164.312: access controls documentation |
| `policy.version` | Art. 12: log versioning | 45 CFR 164.308: audit log |
| `tool_transcript[].decision` | Art. 14: human oversight record | 45 CFR 164.308(a)(1)(ii)(D): activity review |
| `data_class` (per call) | Art. 10: data governance | 45 CFR 164.502: minimum necessary |
| `runtime.tee_type` + `runtime.measurement` | Art. 12: tamper-evident logging | 45 CFR 164.312(c): integrity |
| `subject` | Art. 12: traceability to specific run | 45 CFR 164.308(a)(5): access monitoring |

---

## Extending this example

### Connect a real EHR MCP server

Replace the `server.url` values in `catalog.json` with your actual MCP server endpoint and update `tls_fingerprint`:

```bash
openssl s_client -connect ehr.hospital.example:443 < /dev/null 2>/dev/null \
  | openssl x509 -fingerprint -sha256 -noout \
  | sed 's/sha256 Fingerprint=//;s/://g'
```

### Switch to hardware attestation

Remove `CMCP_DEV_MODE=1` and provision a VM with TPM 2.0 or AMD SEV-SNP. The `runtime.tee_type` in the TRACE record will change from `dev-mode` to `tpm2` or `sev-snp`.

### Add SPIFFE identity for the agent

If your hospital deploys SPIRE, the runtime will automatically obtain a SPIFFE SVID and include the `subject` field in the TRACE record as a hardware-attested SPIFFE URI instead of a self-signed placeholder.

---

## License

Apache 2.0. See [LICENSE](../LICENSE) in the repo root.
