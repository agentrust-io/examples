# financial-services: EU Credit Risk Agent Demo

End-to-end demo of a credit risk agent processing client financial documents through a cMCP Runtime with Cedar policy enforcement and signed TRACE Trust Records for EU regulatory compliance (EU AI Act, MiFID II, DORA, GDPR).

---

## What the demo shows

**1. Cryptographic proof of which tools an AI agent called**
The cMCP Runtime intercepts every MCP tool call, records it in a hash-chained audit log persisted to SQLite, and seals the session into a signed `RuntimeClaim` (the TRACE Trust Record). An auditor can verify after the fact exactly which tools ran, in what order, and what was denied - without trusting the agent process.

**2. Cedar policy as machine-readable compliance**
The rules in `policy/allow.cedar` encode the bank's requirements directly. The MiFID II escalation rule blocks any risk report above EUR 500,000 and returns the policy's `@annotation` metadata as structured advice, so the calling system knows *why* and *who must review*.

**3. EU AI Act Article 12 transparency obligation**
Article 12 requires high-risk AI systems to log sufficient information for post-hoc monitoring. The TRACE record covers the policy version enforced, the audit chain root/tip, per-call decisions, and the runtime attestation - signed by the runtime's key.

**4. Attestation-gated data access (DORA Art. 9)**
A Cedar rule forbids confidential (`mnpi`) tools when no attestation evidence is present: confidential financial data only flows through attested runtimes.

---

## Architecture

```
  +------------------------------------------------------------------+
  |                   Credit Risk Agent (LLM)                        |
  |   agent/credit_risk_agent.py -- JSON-RPC 2.0 over HTTP           |
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
  |          Mock EU Credit Risk MCP Server  :8080                   |
  |   server/mock_mcp_server.py                                       |
  |   finance.document_reader                                         |
  |   finance.credit_score_lookup                                     |
  |   finance.risk_report_writer                                      |
  +------------------------------------------------------------------+
```

---

## The catalog

`catalog.json` registers three tools with approved definitions, classifications, and definition hashes (`sha256` of the canonical JSON of `approved_definition` - the runtime rejects drifted definitions).

| Tool | compliance_domain | sensitivity_level |
|---|---|---|
| `finance.document_reader` | mnpi | confidential |
| `finance.credit_score_lookup` | pii | confidential |
| `finance.risk_report_writer` | internal | confidential |

---

## Run it

```bash
git clone https://github.com/agentrust-io/examples.git
cd examples
pip install cmcp-runtime httpx
```

**Terminal 1 - mock MCP server:**

```bash
cd financial-services
python server/mock_mcp_server.py
```

**Terminal 2 - runtime** (run from inside `financial-services/` - config paths resolve relative to the working directory):

```bash
cd financial-services
CMCP_DEV_MODE=1 cmcp start --config cmcp-config.yaml
```

**Terminal 3 - happy path (EUR 250,000, below the threshold):**

```bash
cd examples
python financial-services/agent/credit_risk_agent.py
```

```
[1/3] Calling finance.document_reader ...
      -> decision: allow
[2/3] Calling finance.credit_score_lookup ...
      -> decision: allow
[3/3] Calling finance.risk_report_writer ...
      -> decision: allow

Closing session <id> and fetching the signed TRACE Trust Record ...
```

**Escalation path (EUR 750,000):**

```bash
python financial-services/agent/credit_risk_agent.py --amount-eur 750000
```

```
[3/3] Calling finance.risk_report_writer ...
      -> decision: deny (POLICY_DENY)
         advice from policy:
           id: large-exposure-hitl
           reason: human-review-required
           regulation: mifid-ii-art-25
           escalation_threshold_eur: 500000

  The risk report was NOT written to the core banking system.
```

---

## The Cedar policy

`policy/allow.cedar` has no catch-all permit: each tool is explicitly permitted only for the `credit-risk-analyst` workflow (declared by the agent via `_cmcp.workflow_id`). Wrong workflow, missing workflow, or an unlisted action is denied by Cedar's default-deny:

```cedar
permit (
  principal,
  action == Action::"Finance.documentReader",
  resource
) when {
  context has workflow_id &&
  context.workflow_id == "credit-risk-analyst"
};
```

On top of the workflow-scoped permits, the escalation rule:

```cedar
@id("large-exposure-hitl")
@reason("human-review-required")
@regulation("mifid-ii-art-25")
@escalation_threshold_eur("500000")
forbid (
  principal,
  action == Action::"Finance.riskReportWriter",
  resource
) when {
  context.arguments has amount_eur &&
  context.arguments.amount_eur > 500000
};
```

Action names follow the cMCP convention: `finance.risk_report_writer` becomes `Action::"Finance.riskReportWriter"` (PascalCase per underscore segment). Tool arguments are available under `context.arguments`; the `@annotation` values are returned in the deny response's `error.data.advice`.

---

## The TRACE Trust Record

See `trace-output/example-trust-record.json` - captured from a real run. Structure: `{"cmcp_version", "trace": {...}, "gateway": {...}, "signature"}`.

| TRACE field | EU AI Act | MiFID II | DORA | GDPR |
|---|---|---|---|---|
| `trace.policy.bundle_hash` | Art. 9 - risk mgmt system version | Art. 25 - controls documentation | Art. 9 - change management | - |
| `trace.policy.version` | Art. 12 - log versioning | Art. 25 - audit trail | Art. 11 - ICT change log | - |
| `trace.runtime` + `signature` | Art. 12 - tamper-evident logging | - | Art. 9 - security of ICT systems | Art. 32 - security of processing |
| `gateway.call_summary` | Art. 12 - post-hoc review data | Art. 25 - basis of recommendation | Art. 17 - incident management | Art. 5(1)(c) - data minimisation |
| `trace.data_class` | Art. 10 - data governance | - | - | Art. 5(1)(b) - purpose limitation |
| `trace.subject` | Art. 12 - traceability to run | Art. 25 - audit trail | Art. 17 - incident traceability | Art. 5(1)(f) - accountability |

Export the full audit chain for a closed session:

```bash
curl "http://localhost:8443/audit/export?session_id=<id>" | python3 -m json.tool
```

---

## Extending this example

- **Real MCP server:** point `server.url` in `catalog.json` at your endpoint; get the TLS fingerprint with `openssl s_client -connect host:443 | openssl x509 -fingerprint -sha256 -noout`.
- **Change the threshold:** edit the `when` clause and the `@escalation_threshold_eur` annotation together.
- **Hardware attestation:** drop `CMCP_DEV_MODE=1` on a VM with TPM 2.0 / SEV-SNP / TDX.
- **Production hardening:** set `CMCP_BEARER_TOKEN`, `CMCP_POLICY_HASH`, `CMCP_CATALOG_HASH`.

---

## Troubleshooting

**Tool call returns 502 `UPSTREAM_UNAVAILABLE`** - the mock MCP server is not running on port 8080 (Terminal 1).

**Runtime exits at startup** - config paths resolve relative to the working directory; run `cmcp start` from inside `financial-services/`.

**Cedar policy parse error** - check for stray Unicode (smart quotes) in `allow.cedar`; annotations must be `@key("value")` with double quotes.

---

## License

Apache 2.0. See [LICENSE](../LICENSE) in the repo root.
