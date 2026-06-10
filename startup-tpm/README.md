# startup-tpm: 15-Minute cMCP Quickstart

Get a cMCP Runtime running with TPM-backed TRACE Trust Records in under 15 minutes. Works on any cloud VM with TPM 2.0 (Azure Trusted Launch, AWS Nitro, GCP Shielded VM) or with `CMCP_DEV_MODE=1` for local development (no hardware required for testing).

---

## What you will have at the end

- A cMCP Runtime running on port 8443
- A Cedar policy that permits all tool calls (replace before production)
- A one-tool catalog (`test.echo`)
- A TRACE Trust Record you can inspect and verify

Estimated time: 15 minutes on a fresh VM, 5 minutes if Python is already installed.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | `python3 --version` |
| pip | any recent | `pip --version` |
| curl | any | For the test tool call |
| TPM 2.0 | optional | Required for hardware attestation; omit with `CMCP_DEV_MODE=1` |

No MCP server is required; the runtime runs a built-in echo responder for the `test.echo` tool.

---

## Step 1 - Install

```bash
pip install cmcp-runtime
```

Verify:

```bash
cmcp --version
```

Expected output: `cmcp-runtime 0.x.y`

---

## Step 2 - Get the quickstart files

```bash
git clone https://github.com/agentrust-io/examples.git
cd examples/startup-tpm
```

The directory contains:

```
startup-tpm/
  cmcp-config.yaml      runtime configuration
  catalog.json          one-tool catalog (test.echo)
  policy/
    manifest.json       policy bundle metadata
    allow.cedar         permit-all policy
    schema.cedarschema  Cedar schema (minimal)
  agent/
    echo_agent.py       minimal agent script
```

---

## Step 3 - Review the config

`cmcp-config.yaml`:

```yaml
policy_bundle_path: ./policy
catalog_path: ./catalog.json
listen_addr: 0.0.0.0:8443
attestation:
  provider: auto
  enforcement_mode: advisory
```

`enforcement_mode: advisory` means the runtime logs policy violations but does not block calls. Change to `enforcing` before production.

`provider: auto` selects the best available attestation source: TPM 2.0 if present, software-only otherwise.

---

## Step 4 - Start the runtime

### With hardware TPM (Azure Trusted Launch, AWS Nitro, GCP Shielded VM)

```bash
cmcp start --config startup-tpm/cmcp-config.yaml
```

The runtime will print the TPM attestation measurement on startup.

### Without hardware TPM (local dev, CI)

```bash
CMCP_DEV_MODE=1 cmcp start --config startup-tpm/cmcp-config.yaml
```

`CMCP_DEV_MODE=1` sets `tee_type: dev-mode` in the TRACE record and marks the measurement `DEVELOPMENT_ONLY_NOT_FOR_PRODUCTION`. The runtime is fully functional but the attestation is not hardware-backed.

Expected startup output:

```
[cmcp] policy bundle loaded: quickstart-v1.0
[cmcp] catalog loaded: 1 tool (test.echo)
[cmcp] attestation: dev-mode (CMCP_DEV_MODE=1)
[cmcp] listening on 0.0.0.0:8443
```

---

## Step 5 - Make a test tool call

**Option A - agent script (recommended):**

```bash
python startup-tpm/agent/echo_agent.py
```

The script calls `test.echo`, prints the policy decision, and fetches the TRACE Trust Record in one shot.

**Option B - curl:**

```bash
curl -X POST http://localhost:8443/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"test.echo","arguments":{"message":"hello"}}}'
```

Expected response:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [{"type": "text", "text": "hello"}],
    "cmcp_decision": "allow",
    "cmcp_policy_version": "quickstart-v1.0"
  }
}
```

---

## Step 6 - Get the TRACE Trust Record

```bash
curl http://localhost:8443/trace | python3 -m json.tool
```

The TRACE record covers the entire session (all tool calls since the runtime started). Example output:

```json
{
  "eat_profile": "tag:agentrust.io,2026:trace-v0.1",
  "iat": 1750000000,
  "subject": "spiffe://localhost/agents/anonymous/run-...",
  "runtime": {
    "platform": "software-only",
    "tee_type": "dev-mode",
    "measurement": "DEVELOPMENT_ONLY_NOT_FOR_PRODUCTION"
  },
  "policy": {
    "framework": "cedar",
    "enforcement_mode": "advisory",
    "version": "quickstart-v1.0"
  },
  "data_class": "internal",
  "tool_transcript": [
    {"tool": "test.echo", "data_class": "internal", "decision": "allow"}
  ],
  "cnf": {"kid": "cmcp-..."}
}
```

---

## Step 7 - Verify the TRACE record (optional)

```bash
curl -s http://localhost:8443/trace > trace.json
cmcp-verify trace.json
```

In dev mode the output will be:

```
[cmcp-verify] signature: valid
[cmcp-verify] attestation: dev-mode (not hardware-backed)
[cmcp-verify] policy version: quickstart-v1.0
[cmcp-verify] tool transcript: 1 call, all allowed
[cmcp-verify] RESULT: PASS (dev-mode)
```

---

## Next steps

| Goal | Where to look |
|---|---|
| Real financial-services example with Cedar escalation rules | `financial-services/` |
| Hardware attestation on Azure | See [Azure Trusted Launch docs](https://learn.microsoft.com/azure/virtual-machines/trusted-launch) |
| Writing your own Cedar policies | [Cedar policy language reference](https://www.cedarpolicy.com/en/tutorial) |
| Protecting a real MCP server | Edit `catalog.json` to point `server.url` at your MCP server |
| Production enforcement | Change `enforcement_mode: advisory` to `enforcement_mode: enforcing` |

---

## Troubleshooting

**Port 8443 already in use**

```bash
# Change listen_addr in cmcp-config.yaml, e.g.:
listen_addr: 0.0.0.0:9443
```

**`cmcp` command not found**

```bash
# Make sure pip's bin directory is on PATH:
python3 -m cmcp --version
# or:
pip show cmcp-runtime | grep Location
export PATH="$PATH:$(pip show cmcp-runtime | grep Location | cut -d' ' -f2)/../../../bin"
```

**`CMCP_DEV_MODE` not recognised on Windows**

```powershell
$env:CMCP_DEV_MODE = "1"
cmcp start --config startup-tpm/cmcp-config.yaml
```

**Runtime exits immediately**

Check that `policy/` and `catalog.json` exist relative to the working directory from which you run `cmcp start`. The `policy_bundle_path` and `catalog_path` in `cmcp-config.yaml` are resolved relative to the config file's location, not the working directory.
