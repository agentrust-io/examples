# ARDS — Governed Agent Discovery

This directory shows how agentrust.io participates in the [Agentic Resource Discovery Specification](https://github.com/ards-project/ard-spec) (ARDS v0.9) as a **governed-agent federated registry** — a specialized ARD registry that only indexes agents carrying TRACE-v0.2 runtime governance attestations.

## What's here

| File | Description |
|---|---|
| `ai-catalog.json` | agentrust.io's `/.well-known/ai-catalog.json` — the static catalog that ARD crawlers ingest. Lists cMCP, Agent Manifest SDK, and TRACE Registry as governed MCP servers, plus the agentrust.io registry entry for ARD federation. |

## The integration point

ARDS `trustManifest.attestations` accepts any attestation type. TRACE-v0.2 is a **runtime governance attestation** — it proves an agent ran under a specific Cedar policy in a verified TEE, with a signed tool-call transcript, in one independently verifiable artifact.

```json
{
  "trustManifest": {
    "identity": "spiffe://trust.agentrust.io/gateway/cmcp/prod",
    "identityType": "spiffe",
    "attestations": [
      { "type": "SPIFFE-X509", "uri": "https://agentrust.io/.well-known/spiffe/jwks" },
      {
        "type": "TRACE-v0.2",
        "uri": "https://trace.agentrust.io/records/cmcp-prod-latest",
        "digest": "sha256:3f4a8b2c..."
      }
    ]
  }
}
```

The `uri` resolves to a TRACE Trust Record — an EAT (RFC 9711) signed JSON artifact containing the Cedar policy hash, TEE measurement, and tool transcript hash. The `digest` is the SHA-256 of that record. Both fields allow an ARD registry or orchestrator to verify the governance claim offline, without calling agentrust.io.

## Filtering for governed agents in ARD search

Any ARD registry that ingests the agentrust.io catalog will make this filter work:

```json
{
  "query": {
    "text": "policy-governed MCP gateway with hardware attestation",
    "filter": {
      "trustManifest.attestations.type": ["TRACE-v0.2"]
    }
  }
}
```

This returns only agents with hardware-verifiable runtime governance records — across any registry in the federation that has ingested TRACE-attested entries.

## agentrust.io as a federated governed-agent registry

The last entry in `ai-catalog.json` registers the agentrust.io registry itself:

```json
{
  "identifier": "urn:ai:agentrust.io:registry:governed-agents",
  "type": "application/ai-registry+json",
  "url": "https://registry.agentrust.io/api/v1/"
}
```

ARD registries discovering this entry can route queries with `trustManifest.attestations.type: TRACE-v0.2` to `registry.agentrust.io` via federation referrals, delegating governed-agent discovery without replicating the trust logic.

## TRACE spec

- Spec: [agentrust-io/trace-spec](https://github.com/agentrust-io/trace-spec)
- ARDS PR: [ards-project/ard-spec#6](https://github.com/ards-project/ard-spec/pull/6)
- AGT ADR: `docs/adr/0032-agt-emits-trace-v01-trust-records.md` in [microsoft/agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit)
