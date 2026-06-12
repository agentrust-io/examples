[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![cMCP](https://img.shields.io/badge/Uses-cMCP_Runtime-7c3aed)](https://github.com/agentrust-io/cmcp)
[![Agent Manifest](https://img.shields.io/badge/Uses-Agent_Manifest-0ea5e9)](https://github.com/agentrust-io/agent-manifest)

# agentrust-io Examples

End-to-end integration examples showing cMCP, Agent Manifest, and TRACE working together across deployment scenarios. Each example is self-contained and runnable on a fresh cloud VM. Running them shows how the three projects compose: cMCP enforces policy at the tool call boundary, Agent Manifest carries the identity and capability declaration, and TRACE emits a signed Trust Record for every tool invocation so you can see what the full audit trail looks like in practice.

## Examples

| Example | What it shows | Platform | Compliance |
|---|---|---|---|
| `financial-services/` | Payment agent with Cedar policy: blocks PII in tool call parameters | SEV-SNP / TDX | EU AI Act Art. 9/12, DORA Art. 9 |
| `healthcare/` | Clinical decision agent with HITL approvals and EU AI Act Art. 14 compliance records | SEV-SNP / TDX | EU AI Act Art. 14, HIPAA |
| `industrial-embodied-ai/` | Material-movement agent with cMCP authorization, an independent safety-controller boundary and offline-verifiable closed-session evidence | TEE / software-only development mode | OT security and industrial robot safety references |
| `multi-tenant-saas/` | SaaS platform with per-tenant policy isolation | TDX | Customer contract SLA |
| `startup-tpm/` | 15-minute quickstart on any cloud VM with Trusted Launch | TPM 2.0 | Development / staging |

## Quickstart

The fastest path: any Azure, AWS, or GCP VM with Trusted Launch enabled.

```bash
pip install cmcp-runtime agent-manifest
cp examples/startup-tpm/cmcp-config.yaml .
cmcp start --config cmcp-config.yaml --enforcement advisory
```

This starts the runtime in advisory mode (no blocking, full logging) and emits a TRACE Trust Record for every MCP tool call.

## Prerequisites

- Python 3.11+
- An MCP server to protect (existing servers work unchanged)
- For Level 1 attestation: a VM with TPM 2.0, AMD SEV-SNP, or Intel TDX
- For GPU-CC attestation (v0.2): NVIDIA H100/H200 with CC mode enabled

## Status

Launching at Confidential Computing Summit, San Francisco, June 23 2026.

## License

Apache 2.0
