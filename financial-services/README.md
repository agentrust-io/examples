# financial-services: EU Credit Risk Agent Demo

End-to-end demo of a credit risk agent processing client financial documents through a cMCP gateway with Cedar policy enforcement and TRACE Trust Records for EU regulatory compliance (EU AI Act, MiFID II, DORA, GDPR).

End-to-end example: AI agent compliance for European private banks using cMCP and TRACE attestation.

---

## What the demo shows

This example demonstrates:

**1. Cryptographic proof of which tools an AI agent called**
The cMCP gateway intercepts every MCP tool call and records it in a signed TRACE Trust Record. An auditor or regulator can verify after the fact exactly which tools ran, in what order, with what data classifications — without trusting the agent process itself.

**2. Cedar policy as machine-readable compliance**
The three Cedar rules in `policy/allow.cedar` encode the bank's compliance requirements directly: which workflows may call which tools, when a large credit recommendation must go to a human reviewer, and how to prevent accidental data-class downgrade. Policy-as-code means the same rules that block a call are the rules that go into the audit file.

**3. EU AI Act Article 12 transparency obligation**
Article 12 requires high-risk AI systems to automatically log sufficient information to enable post-hoc monitoring. The TRACE Trust Record is that log. It covers the model identity, the policy version that was enforced, and the full tool call transcript with per-call data-class labels.

**4. MiFID II suitability and audit trail**
MiFID II Article 25 requires that investment firms document the basis for any investment recommendation. For an AI-assisted credit decision, the TRACE record provides the tool-call audit trail showing that credit bureau data was consulted and a human reviewer was required for exposures above €500k.

**5. DORA Article 9 ICT risk — immutable logs**
The gateway runs in an attested environment (TEE or TPM). The TRACE record is signed by the gateway's attestation key. If a log is tampered with, the signature verification fails.

**6. GDPR data minimisation in tool definitions**
The catalog schema enforces `sensitivity_level` and `compliance_domain` on every tool. The Cedar policy forbids confidential-data tools if the session sensitivity has been downgraded to `public`. This is the machine-enforceable equivalent of the GDPR data-minimisation principle.

---

## Architecture

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                   Credit Risk Agent (LLM)                       │
  │   credit_risk_agent.py — JSON-RPC 2.0 over HTTP                 │
  └──────────────────────────┬──────────────────────────────────────┘
                             │  tools/call (MCP)
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │              cMCP Gateway  :8443                                │
  │                                                                  │
  │  ┌──────────────┐  ┌─────────────────┐  ┌───────────────────┐  │
  │  │ Cedar engine │  │ Catalog checker │  │ TRACE recorder    │  │
  │  │ allow.cedar  │  │ catalog.json    │  │ /trace endpoint   │  │
  │  └──────────────┘  └─────────────────┘  └───────────────────┘  │
  └──────────────────────────┬──────────────────────────────────────┘
                             │  proxied tool call
                             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │         EU Credit Risk MCP Server  :8080                        │
  │   finance.document_reader                                        │
  │   finance.credit_score_lookup                                    │
  │   finance.risk_report_writer                                     │
  └─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| pip | any recent | `pip --version` |
| httpx | 0.27+ | installed by `pip install cmcp-gateway` |
| cmcp-gateway | latest | `pip install cmcp-gateway` |
| agent-manifest | latest | `pip install agent-manifest` |
| curl | any | For verification steps |

No hardware TEE or TPM is required for this demo. The gateway runs in `CMCP_DEV_MODE=1`.

---

## Step 1 — Clone the examples repo

```bash
git clone https://github.com/agentrust-io/examples.git
cd examples
```

---

## Step 2 — Install dependencies

```bash
pip install cmcp-gateway agent-manifest httpx
```

Verify:

```bash
cmcp --version
cmcp-verify --version
```

---

## Step 3 — Review the files

```
financial-services/
  cmcp-config.yaml              Gateway configuration
  catalog.json                  Three-tool catalog
  policy/
    manifest.json               Policy bundle metadata
    allow.cedar                 Four Cedar rules
    schema.cedarschema          Cedar schema
  agent/
    credit_risk_agent.py        Demo agent (run this)
  trace-output/
    example-trust-record.json   Reference TRACE output
```

---

## Step 4 — Understand the Cedar policy

`policy/allow.cedar` contains four rules:

**Rule 1 — Workflow permit**

```cedar
permit (
  principal,
  action == Action::"tool_call",
  resource
) when {
  context.workflow_id == "credit-risk-analyst"
};
```

Only the `credit-risk-analyst` workflow may call any of the three tools. Any other workflow ID results in a deny.

**Rule 2 — Large-exposure escalation (advisory)**

```cedar
forbid (
  principal,
  action == Action::"tool_call",
  resource == Tool::"finance.risk_report_writer"
) when {
  context.amount_eur > 500000
} advice {
  "reason": "human-review-required",
  "escalation_threshold_eur": 500000
};
```

Any call to `finance.risk_report_writer` where `amount_eur` exceeds €500,000 triggers an advisory deny. In `enforcement_mode: enforcing` this blocks the call and returns a 403 with the advice payload. The agent script uses `amount_eur=250000` so this rule does not fire in the happy path — see "Extending this example" for how to trigger it.

**Rule 3 — Data-class downgrade prevention**

```cedar
forbid (
  principal,
  action == Action::"tool_call",
  resource
) when {
  context.session_max_sensitivity == "public" &&
  resource.compliance_domain == "confidential"
};
```

Prevents a session that has been flagged `public` from calling tools that handle confidential data. This enforces the GDPR data-minimisation principle at the gateway layer.

**Rule 4 — Catch-all permit**

```cedar
permit (principal, action, resource);
```

Any call not matched by a forbid is allowed. Removes the need to enumerate every possible action type.

---

## Step 5 — Review the catalog

`catalog.json` registers three tools with their approved definitions, data classifications, and definition hashes. The definition hash is `sha256(json.dumps(approved_definition, sort_keys=True, separators=(',',':')))`. The gateway rejects any tool call where the server returns a definition that does not match the hash — preventing prompt-injection via MCP tool description tampering.

| Tool | compliance_domain | sensitivity_level | definition_hash (first 16 chars) |
|---|---|---|---|
| `finance.document_reader` | hipaa_phi | confidential | `sha256:75312282...` |
| `finance.credit_score_lookup` | pii | confidential | `sha256:0db5f137...` |
| `finance.risk_report_writer` | internal | internal | `sha256:b98f4fff...` |

---

## Step 6 — Start the gateway

```bash
CMCP_DEV_MODE=1 cmcp start --config financial-services/cmcp-config.yaml
```

Run from the root of the examples repo so relative paths in the config resolve correctly.

Expected startup output:

```
[cmcp] policy bundle loaded: credit-risk-v4.2
[cmcp] catalog loaded: 3 tools
[cmcp]   finance.document_reader       (confidential)
[cmcp]   finance.credit_score_lookup   (confidential)
[cmcp]   finance.risk_report_writer    (internal)
[cmcp] attestation: dev-mode (CMCP_DEV_MODE=1)
[cmcp] enforcement: enforcing
[cmcp] listening on 0.0.0.0:8443
```

Leave this terminal open.

---

## Step 7 — Run the mock credit risk agent

In a second terminal:

```bash
python financial-services/agent/credit_risk_agent.py
```

The agent calls the three tools in sequence:

1. `finance.document_reader` — reads balance sheet `BS-2024-Q4` for client `EUR-2024-00847`
2. `finance.credit_score_lookup` — retrieves Equifax score for the client
3. `finance.risk_report_writer` — writes a risk score of 72.3 with recommendation `approve` and `amount_eur=250000`

Expected output:

```
Connecting to cMCP gateway at http://localhost:8443
Client: EUR-2024-00847  |  Document: BS-2024-Q4  |  Bureau: equifax

[1/3] Calling finance.document_reader ...
      -> decision: allow
[2/3] Calling finance.credit_score_lookup ...
      -> decision: allow
[3/3] Calling finance.risk_report_writer ...
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

## Step 8 — Inspect the TRACE Trust Record

```bash
curl -s http://localhost:8443/trace | python3 -m json.tool
```

See the "Expected output" section below for the full annotated TRACE record.

---

## Step 9 — Verify with cmcp-verify

```bash
curl -s http://localhost:8443/trace > trace.json
cmcp-verify trace.json
```

Expected output:

```
[cmcp-verify] signature: valid
[cmcp-verify] attestation: dev-mode (not hardware-backed)
[cmcp-verify] policy version: credit-risk-v4.2
[cmcp-verify] tool transcript: 3 calls, all allowed
[cmcp-verify] data_class: confidential (session maximum)
[cmcp-verify] RESULT: PASS (dev-mode)
```

For a production deployment with hardware TEE, the attestation line reads:
```
[cmcp-verify] attestation: SEV-SNP verified (PCR0: aa11bb22...)
```

---

## Expected output — Full TRACE Trust Record

```json
{
  "eat_profile": "tag:agentrust.io,2026:trace-v0.1",
  "iat": 1750000000,
  "subject": "spiffe://bank.eu/agents/credit-risk-analyst/run-abc123",
  "model": {
    "provider": "bank-internal",
    "name": "credit-risk-llm-eu",
    "version": "2.1.0",
    "digest": {
      "sha-256": "a3f9b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1"
    }
  },
  "runtime": {
    "platform": "software-only",
    "tee_type": "dev-mode",
    "measurement": "DEVELOPMENT_ONLY_NOT_FOR_PRODUCTION",
    "region": "westeurope"
  },
  "policy": {
    "framework": "cedar",
    "bundle_hash": "sha256:b8c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2",
    "enforcement_mode": "enforce",
    "version": "credit-risk-v4.2"
  },
  "data_class": "confidential",
  "tool_transcript": [
    {
      "tool": "finance.document_reader",
      "data_class": "confidential",
      "decision": "allow"
    },
    {
      "tool": "finance.credit_score_lookup",
      "data_class": "confidential",
      "decision": "allow"
    },
    {
      "tool": "finance.risk_report_writer",
      "data_class": "internal",
      "decision": "allow"
    }
  ],
  "cnf": {
    "kid": "cmcp-a1b2c3d4"
  }
}
```

### Field annotations

| Field | Value in demo | Meaning |
|---|---|---|
| `eat_profile` | `tag:agentrust.io,2026:trace-v0.1` | TRACE schema version |
| `iat` | Unix timestamp | Time the record was sealed |
| `subject` | `spiffe://bank.eu/...` | SPIFFE ID of the agent run |
| `model.provider` | `bank-internal` | Model hosting entity |
| `model.digest.sha-256` | hex string | Immutable model fingerprint |
| `runtime.tee_type` | `dev-mode` | `sev-snp` or `tdx` in production |
| `runtime.measurement` | `DEVELOPMENT_ONLY_...` | PCR0/RTMR measurement in production |
| `policy.bundle_hash` | sha256 hex | Hash of the Cedar bundle used |
| `policy.version` | `credit-risk-v4.2` | From `policy/manifest.json` |
| `data_class` | `confidential` | Highest sensitivity across all calls |
| `tool_transcript` | array | One entry per tool call, in order |
| `cnf.kid` | `cmcp-a1b2c3d4` | Key ID of the gateway signing key |

---

## Regulatory field mapping

| TRACE field | EU AI Act | MiFID II | DORA | GDPR |
|---|---|---|---|---|
| `model.digest` | Art. 12 — logging of AI system identity | Art. 25 — documentation of system used | Art. 9 — ICT asset inventory | Art. 5(1)(f) — integrity |
| `policy.bundle_hash` | Art. 9 — risk management system version | Art. 25 — controls documentation | Art. 9 — change management | — |
| `policy.version` | Art. 12 — log versioning | Art. 25 — audit trail | Art. 11 — ICT change log | — |
| `runtime.tee_type` + `runtime.measurement` | Art. 12 — tamper-evident logging | — | Art. 9 — security of ICT systems | Art. 32 — security of processing |
| `tool_transcript` | Art. 12 — sufficient data for post-hoc review | Art. 25 — basis of recommendation | Art. 17 — incident management | Art. 5(1)(c) — data minimisation |
| `data_class` (per call) | Art. 10 — data governance | — | — | Art. 5(1)(b) — purpose limitation |
| `subject` (SPIFFE) | Art. 12 — traceability to specific run | Art. 25 — audit trail | Art. 17 — incident traceability | Art. 5(1)(f) — accountability |
| `cnf.kid` | Art. 12 — authentic log provenance | — | Art. 9 — key management | — |

---

## Extending this example

### Swap in a real MCP server

Replace the `server.url` values in `catalog.json` with your actual MCP server endpoint:

```json
"server": {
  "display_name": "Production Credit Risk Server",
  "url": "https://mcp.bank.eu/credit-risk",
  "tls_fingerprint": "SHA256:<your-actual-fingerprint>",
  "transport": "http-sse"
}
```

Get the TLS fingerprint:

```bash
openssl s_client -connect mcp.bank.eu:443 < /dev/null 2>/dev/null \
  | openssl x509 -fingerprint -sha256 -noout \
  | sed 's/sha256 Fingerprint=//;s/://g'
```

### Trigger the €500k escalation rule

Edit `credit_risk_agent.py` and change `AMOUNT_EUR = 250_000` to `AMOUNT_EUR = 750_000`. Re-run the agent. The gateway will return an advisory deny for the `finance.risk_report_writer` call:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "error": {
    "code": -32003,
    "message": "tool_call denied",
    "data": {
      "decision": "advisory_deny",
      "reason": "human-review-required",
      "escalation_threshold_eur": 500000
    }
  }
}
```

### Switch to enforcing mode

Change `enforcement_mode: enforcing` in `cmcp-config.yaml` (it is already set to `enforcing`). In dev mode the gateway enforces the policy but the attestation is not hardware-backed. Change `CMCP_DEV_MODE=1` to use a real TPM or TEE for production.

### Add a new tool

1. Define the tool in your MCP server.
2. Add an entry to `catalog.json` with the correct `definition_hash`.
3. Add a Cedar rule in `allow.cedar` if needed.
4. Restart the gateway with `cmcp start --config financial-services/cmcp-config.yaml --reload`.

The definition hash is:

```python
import hashlib, json

def definition_hash(approved_definition: dict) -> str:
    canonical = json.dumps(approved_definition, sort_keys=True, separators=(',', ':'))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
```

### Enable hardware attestation (Azure Trusted Launch)

1. Provision an Azure VM with Trusted Launch enabled (Trusted Launch is the default for most VM sizes as of 2025).
2. Install the vTPM extension if not already present.
3. Remove `CMCP_DEV_MODE=1` from the startup command.
4. The gateway will automatically use the vTPM. The `runtime.tee_type` field in the TRACE record will be `tpm2` and `runtime.measurement` will contain the PCR0 value.

### Connect an agent manifest

If you publish an agent manifest with `agent-manifest`, the gateway can cross-check the manifest's `allowed_tools` list against the catalog:

```bash
agent-manifest validate --manifest agent-manifest.json --catalog financial-services/catalog.json
```

---

## Troubleshooting

**Gateway cannot find the policy bundle**

Make sure you run `cmcp start` from the root of the examples repo, or use an absolute path:

```bash
cmcp start --config /path/to/examples/financial-services/cmcp-config.yaml
```

**`httpx.ConnectError` in the agent script**

The gateway is not running, or is running on a different port. Check:

```bash
curl http://localhost:8443/health
```

**`definition_hash mismatch` error**

The catalog hash was computed from a different tool definition than what the server returned. Recompute using the Python snippet in "Extending this example" above.

**Cedar policy parse error on startup**

Cedar is whitespace-sensitive in some versions. Check that there are no stray Unicode characters (e.g., smart quotes) in `allow.cedar`. Use a plain ASCII editor.

**TRACE record shows `data_class: internal` instead of `confidential`**

The session-level `data_class` is the maximum across all tool calls. If only `finance.risk_report_writer` (internal) was called, the session data class is `internal`. Call `finance.document_reader` or `finance.credit_score_lookup` first to raise it to `confidential`.

---

## License

Apache 2.0. See [LICENSE](../LICENSE) in the repo root.
