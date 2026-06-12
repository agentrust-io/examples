# multi-tenant-saas: Per-Tenant Cedar Policy Isolation

End-to-end demo of a SaaS platform serving tenants with different compliance postures, each enforced by a separate Cedar policy bundle - and different *enforcement modes* - in the cMCP Runtime.

The same three tool calls produce different outcomes per tenant:

| Tool | acme-corp (advisory) | globex-financial (enforcing) |
|---|---|---|
| `saas.analytics_query` | allow | allow |
| `saas.user_data_export` | advisory_deny (logged, not blocked) | deny |
| `saas.config_update` | allow | deny |

---

## What the demo shows

**1. Policy-as-isolation at the tool boundary**
Each tenant has its own Cedar bundle under `tenants/<name>/policy/` and its own runtime config pointing at it. The `trace.policy.version` field in each TRACE record identifies exactly which tenant policy was enforced (`acme-corp-v1.0` vs `globex-financial-v3.2`).

**2. Progressive compliance posture via enforcement mode**
Acme Corp runs `enforcement_mode: advisory`: a matched forbid is logged in the audit chain and surfaced as `would_have_denied` + advice in the response metadata, but the call proceeds. Globex Financial runs `enforcing` with no catch-all permit - Cedar's default-deny blocks anything not explicitly permitted.

**3. Structured advice on denies**
Both tenants' forbid rules carry `@annotation` metadata (GDPR article, required workflow) that the runtime returns to the caller - in `error.data.advice` for hard denies, in `_cmcp.advice` for advisory ones.

---

## File layout

```
multi-tenant-saas/
  cmcp-config-acme-corp.yaml            advisory mode -> tenants/acme-corp/policy
  cmcp-config-globex-financial.yaml     enforcing mode -> tenants/globex-financial/policy
  catalog.json                          shared three-tool catalog
  tenants/
    acme-corp/policy/                   acme-corp-v1.0 (permissive)
    globex-financial/policy/            globex-financial-v3.2 (default-deny)
  server/
    mock_mcp_server.py                  mock upstream MCP server (stdlib only)
  agent/
    saas_agent.py                       demo agent (run this)
  trace-output/
    acme-corp-example.json              real captured TRACE record (advisory)
    globex-financial-example.json       real captured TRACE record (enforcing)
```

---

## Run it

```bash
git clone https://github.com/agentrust-io/examples.git
cd examples
pip install cmcp-runtime httpx
```

**Terminal 1 - mock MCP server:**

```bash
cd multi-tenant-saas
python server/mock_mcp_server.py
```

**Terminal 2 - runtime with Acme Corp's policy** (run from inside `multi-tenant-saas/`):

```bash
cd multi-tenant-saas
CMCP_DEV_MODE=1 cmcp start --config cmcp-config-acme-corp.yaml
```

**Terminal 3 - agent:**

```bash
cd examples
python multi-tenant-saas/agent/saas_agent.py --tenant acme-corp
```

```
[1/3] Calling saas.analytics_query ...
      -> decision: allow
[2/3] Calling saas.user_data_export ...
      -> decision: advisory_deny (logged, not blocked)
         advice from policy:
           id: gdpr-justification-missing
           reason: gdpr-justification-missing
           regulation: gdpr-art-6
[3/3] Calling saas.config_update ...
      -> decision: allow
```

**Switch tenants** - stop the runtime (Ctrl-C) and restart with Globex Financial's config:

```bash
CMCP_DEV_MODE=1 cmcp start --config cmcp-config-globex-financial.yaml
```

```bash
python multi-tenant-saas/agent/saas_agent.py --tenant globex-financial
```

```
[1/3] Calling saas.analytics_query ...
      -> decision: allow
[2/3] Calling saas.user_data_export ...
      -> decision: deny (POLICY_DENY)
         advice from policy:
           id: export-requires-compliance-workflow
           reason: export-requires-data-compliance-workflow
           regulation: gdpr-art-6
[3/3] Calling saas.config_update ...
      -> decision: deny (POLICY_DENY)
         advice from policy:
           id: config-update-requires-admin-workflow
           reason: config-update-requires-admin-workflow
```

Each run ends by closing the session and printing the signed TRACE Trust Record. Compare `trace.policy.version` and `gateway.call_summary.tool_calls_denied` across the two captured examples in `trace-output/`.

---

## How the policies differ

**Acme Corp** (`tenants/acme-corp/policy/allow.cedar`): a catch-all permit plus one annotated forbid - user data export without a `gdpr_justification` argument. Under advisory mode this logs and flags but does not block.

**Globex Financial** (`tenants/globex-financial/policy/allow.cedar`): no catch-all. Explicit permits per tool, gated on the workflow the agent declares via `_cmcp.workflow_id`:

```cedar
permit (
  principal,
  action == Action::"Saas.userDataExport",
  resource
) when {
  context has workflow_id &&
  context.workflow_id == "data-compliance-workflow"
};
```

The demo agent runs as `analytics-workflow`, so exports and config updates deny. Annotated forbid rules make those denies carry structured advice instead of being silent default-denies.

---

## Running both tenants simultaneously

Run two runtimes on different ports (edit `listen_addr` in one config), one per tenant, against the same mock server:

```bash
python multi-tenant-saas/agent/saas_agent.py --tenant acme-corp --gateway http://localhost:8443
python multi-tenant-saas/agent/saas_agent.py --tenant globex-financial --gateway http://localhost:9443
```

This is the production topology: one attested runtime instance per tenant isolation boundary, each measuring its own policy bundle hash into its TRACE records.

---

## License

Apache 2.0. See [LICENSE](../LICENSE) in the repo root.
