# agentrust-io Examples

End-to-end integration examples showing cMCP, Agent Manifest, and TRACE working together across deployment scenarios. Each example is self-contained and runnable on a fresh cloud VM.

## Examples

| Directory | Scenario | Hardware | Regulatory alignment |
|---|---|---|---|
| `financial-services/` | Payment agent with Cedar policy — blocks PII in tool call parameters | SEV-SNP / TDX | EU AI Act Art. 9/12, DORA Art. 9 |
| `healthcare/` | Clinical data agent with field-level redaction | SEV-SNP | HIPAA §164.312 |
| `multi-tenant-saas/` | SaaS platform with per-tenant policy isolation | TDX | Customer contract SLA |
| `startup-tpm/` | 15-minute quickstart on any cloud VM with Trusted Launch | TPM 2.0 | Development / staging |

## Quickstart

The fastest path: any Azure, AWS, or GCP VM with Trusted Launch enabled.

```bash
pip install cmcp-gateway agent-manifest
cp examples/startup-tpm/cmcp-config.yaml .
cmcp start --config cmcp-config.yaml --enforcement advisory
```

This starts the gateway in advisory mode (no blocking, full logging) and emits a TRACE Trust Record for every MCP tool call.

## Prerequisites

- Python 3.11+
- An MCP server to protect (existing servers work unchanged)
- For Level 1 attestation: a VM with TPM 2.0, AMD SEV-SNP, or Intel TDX

## Status

Launching at Confidential Computing Summit, San Francisco, June 23 2026.

## License

Apache 2.0
