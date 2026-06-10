# multi-tenant-saas: Per-Tenant Cedar Policy Isolation

End-to-end demo of a SaaS platform serving multiple tenants with different compliance requirements, each enforced by a separate Cedar policy bundle loaded into the cMCP Runtime.

The same three tool calls produce different outcomes depending on which tenant's policy is active. Acme Corp allows data export with an advisory warning; Globex Financial hard-blocks it because the calling workflow is not the designated data-compliance workflow.

---

## What the demo shows

**1. Policy-as-isolation at the tool boundary**
Each tenant gets their own Cedar bundle (`tenants/acme-corp/policy/` and `tenants/globex-financial/policy/`). The runtime loads one bundle at startup. Restarting with a different config file switches to the other tenant's rules. Every enforcement decision is recorded in a per-tenant TRACE Trust Record.

**2. Progressive compliance posture**
Acme Corp uses advisory enforcement for missing GDPR justifications — the call is logged and flagged but not blocked. Globex Financial, as a regulated financial firm, uses hard deny for the same scenario. The same cMCP Runtime enforces both postures; only the Cedar bundle differs.

**3. Auditable per-tenant TRACE records**
Because each tenant runs with a different policy version (`acme-corp-v1.0` vs `globex-financial-v3.2`), the `policy.version` field in the TRACE record identifies exactly which tenant policy was enforced. Regulators, auditors, and tenants can verify their own records independently.

---

## Architecture

```
  +------------------------------------------------------------------+
  |               SaaS Agent (LLM)  -- analytics-workflow            |
  |   saas_agent.py -- JSON-RPC 2.0 over HTTP                        |
  +-------------------------------+----------------------------------+
                                  |  tools/call (MCP)
                                  v
  +------------------------------------------------------------------+
  |               cMCP Runtime  :8443                                |
  |                                                                  |
  |  Policy bundle loaded at startup -- one per tenant:              |
  |  tenants/acme-corp/policy/        (permissive)                   |
  |  tenants/globex-financial/policy/ (strict GDPR)                  |
  +-------------------------------+----------------------------------+
                                  |  proxied tool call
                                  v
  +------------------------------------------------------------------+
  |               SaaS Platform MCP Server  :8080                    |
  |   saas.analytics_query                                            |
  |   saas.user_data_export                                           |
  |   saas.config_update                                              |
  +------------------------------------------------------------------+
```

---

## Tenant policy comparison

| Tool | acme-corp | globex-financial |
|---|---|---|
| `saas.analytics_query` | allow | allow |
| `saas.user_data_export` | advisory_deny (no GDPR justification) | deny (wrong workflow) |
| `saas.config_update` | allow | advisory_deny (wrong workflow) |

---

## File layout

```
multi-tenant-saas/
  cmcp-config-acme-corp.yaml            Runtime config for Acme Corp
  cmcp-config-globex-financial.yaml     Runtime config for Globex Financial
  catalog.json                          Shared three-tool catalog
  tenants/
    acme-corp/
      policy/
        manifest.json                   acme-corp-v1.0
        allow.cedar                     Permissive rules
        schema.cedarschema
    globex-financial/
      policy/
        manifest.json                   globex-financial-v3.2
        allow.cedar                     Strict GDPR rules
        schema.cedarschema
  agent/
    saas_agent.py                       Demo agent (run this)
  trace-output/
    acme-corp-example.json              Reference TRACE output for Acme Corp
    globex-financial-example.json       Reference TRACE output for Globex Financial
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

## Step 1 — Clone and install

```bash
git clone https://github.com/agentrust-io/examples.git
cd examples
pip install cmcp-runtime httpx
```

---

## Step 2 — Run the demo for Acme Corp

**Terminal 1 — start the runtime with Acme Corp's policy:**

```bash
CMCP_DEV_MODE=1 cmcp start --config multi-tenant-saas/cmcp-config-acme-corp.yaml
```

Expected startup output:

```
[cmcp] policy bundle loaded: acme-corp-v1.0
[cmcp] catalog loaded: 3 tools
[cmcp] listening on 0.0.0.0:8443
```

**Terminal 2 — run the agent:**

```bash
python multi-tenant-saas/agent/saas_agent.py --tenant acme-corp
```

Expected output:

```
Connecting to cMCP gateway at http://localhost:8443
Tenant:   acme-corp
Workflow: analytics-workflow

Running the same three tool calls against acme-corp's policy bundle.

[1/3] Calling saas.analytics_query ...
      -> decision: allow
[2/3] Calling saas.user_data_export ...
      -> decision: advisory_deny
         reason:   gdpr-justification-missing
         regulation: gdpr-art-6
[3/3] Calling saas.config_update ...
      -> decision: allow

=== TRACE Trust Record ===
{ "policy": { "version": "acme-corp-v1.0", ... }, ... }
```

`user_data_export` is advisory: the call was logged and flagged but not blocked.

---

## Step 3 — Run the demo for Globex Financial

Stop the runtime (Ctrl-C), then restart with Globex Financial's policy:

**Terminal 1:**

```bash
CMCP_DEV_MODE=1 cmcp start --config multi-tenant-saas/cmcp-config-globex-financial.yaml
```

Expected startup output:

```
[cmcp] policy bundle loaded: globex-financial-v3.2
[cmcp] catalog loaded: 3 tools
[cmcp] listening on 0.0.0.0:8443
```

**Terminal 2:**

```bash
python multi-tenant-saas/agent/saas_agent.py --tenant globex-financial
```

Expected output:

```
Connecting to cMCP gateway at http://localhost:8443
Tenant:   globex-financial
Workflow: analytics-workflow

Running the same three tool calls against globex-financial's policy bundle.

[1/3] Calling saas.analytics_query ...
      -> decision: allow
[2/3] Calling saas.user_data_export ...
      -> decision: deny
[3/3] Calling saas.config_update ...
      -> decision: advisory_deny
         reason:   config-update-requires-admin-workflow

=== TRACE Trust Record ===
{ "policy": { "version": "globex-financial-v3.2", ... }, ... }
```

`user_data_export` is a hard deny: the call was blocked. `config_update` is advisory.

The `policy.version` field in the TRACE record shows `globex-financial-v3.2` — this is the field that identifies which tenant's policy was enforced for each session.

---

## Step 4 — Verify the TRACE record

```bash
curl -s http://localhost:8443/trace > trace.json
cmcp-verify trace.json
```

---

## Understanding the Cedar policies

### Acme Corp (`tenants/acme-corp/policy/allow.cedar`)

- Permit analytics-workflow for all tools
- Advisory forbid on `saas.user_data_export` when no GDPR justification is present (logged only)
- Catch-all permit

### Globex Financial (`tenants/globex-financial/policy/allow.cedar`)

- Permit `data-compliance-workflow` only for `saas.user_data_export`
- Permit `admin-workflow` only for `saas.config_update`
- Permit any workflow for `saas.analytics_query`
- Hard deny `saas.user_data_export` for all other workflows
- Advisory deny `saas.config_update` for all other workflows

The difference: Acme Corp trusts its analytics workflow to handle data exports (advisory only). Globex Financial requires a purpose-specific workflow for any personal data access (hard deny by default).

---

## Running both tenants simultaneously

To demonstrate both tenants side by side without restarting, run on different ports:

**Terminal 1 — Acme Corp on 8443:**

```yaml
# cmcp-config-acme-corp.yaml: listen_addr: 0.0.0.0:8443
```

```bash
CMCP_DEV_MODE=1 cmcp start --config multi-tenant-saas/cmcp-config-acme-corp.yaml
```

**Terminal 2 — Globex Financial on 8444:**

Edit `cmcp-config-globex-financial.yaml` to set `listen_addr: 0.0.0.0:8444`, then:

```bash
CMCP_DEV_MODE=1 cmcp start --config multi-tenant-saas/cmcp-config-globex-financial.yaml
```

**Terminal 3:**

```bash
python multi-tenant-saas/agent/saas_agent.py --tenant acme-corp --gateway http://localhost:8443
python multi-tenant-saas/agent/saas_agent.py --tenant globex-financial --gateway http://localhost:8444
```

---

## Production path

In production, per-tenant isolation is enforced by provisioning one cMCP Runtime instance per tenant (or per tenant isolation boundary), each started with that tenant's policy bundle. The runtime's TEE attestation report covers the specific policy hash that was loaded — the TRACE Trust Record is evidence that *this specific bundle* was enforced for *this session*.

Hot-reload (`policy_reload_interval_seconds` in the config) allows policy updates without restarts, but the hash pinning (`CMCP_POLICY_HASH` env var) must be updated to match the new bundle.

---

## License

Apache 2.0. See [LICENSE](../LICENSE) in the repo root.
