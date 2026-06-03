# agentrust-io Examples

End-to-end integration examples showing cMCP, Agent Manifest, and TRACE working together across real deployment scenarios.

## Examples

| Directory | Scenario | Hardware | Regulatory |
|-----------|----------|----------|------------|
| `financial-services-kyc/` | KYC agent with Cedar policy enforcement | OPAQUEProvider | EU AI Act Art. 9/12 |
| `healthcare-clinical/` | Clinical data agent, SEV-SNP attested | SEVSNPProvider | HIPAA §164.312 |
| `multi-tenant-saas/` | SaaS platform multi-tenant governance | OPAQUEProvider | Customer contract SLA |
| `startup-tpm-onramp/` | 15-minute quickstart on any VM | TPMProvider | Future-proofing |
| `cc-summit-demo/` | CC Summit June 23 — Scene A + Scene B demo scripts | OPAQUEProvider | — |

## Quickstart (15 minutes)

```bash
pip install agt-core cmcp-gateway
# Start with TPM advisory mode — any Azure/AWS/GCP VM with Trusted Launch
cp examples/startup-tpm-onramp/cmcp-config.yaml .
cmcp start --config cmcp-config.yaml
```

## Status

Private. Going public Week 4 (Jun 17-23) ahead of CC Summit.

## License

MIT