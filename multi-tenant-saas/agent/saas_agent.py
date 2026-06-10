#!/usr/bin/env python3
"""
SaaS platform agent demo showing per-tenant Cedar policy isolation.

Calls three platform tools through the cMCP gateway using raw JSON-RPC 2.0 over HTTP.
No MCP SDK required -- httpx only.

Usage:
    python saas_agent.py [--gateway http://localhost:8443] --tenant acme-corp|globex-financial

Start the runtime with the matching config before running:
    CMCP_DEV_MODE=1 cmcp start --config multi-tenant-saas/cmcp-config-acme-corp.yaml
    CMCP_DEV_MODE=1 cmcp start --config multi-tenant-saas/cmcp-config-globex-financial.yaml

Expected results:
    acme-corp        : analytics_query=allow, user_data_export=advisory_deny (no justification),
                       config_update=allow
    globex-financial : analytics_query=allow, user_data_export=deny (wrong workflow),
                       config_update=advisory_deny (wrong workflow)
"""

import argparse
import json
import sys
import httpx

DEFAULT_GATEWAY = "http://localhost:8443"
WORKFLOW_ID = "analytics-workflow"


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def make_call(client: httpx.Client, gateway: str, tool_name: str, arguments: dict, req_id: int) -> dict:
    """Send a tools/call to the cMCP gateway. Returns the result dict or a _denied marker."""
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    resp = client.post(f"{gateway}/mcp", json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    if "error" in body:
        err = body["error"]
        data = err.get("data", {})
        if isinstance(data, dict) and data.get("decision") in ("deny", "advisory_deny"):
            return {"_denied": True, "_decision": data.get("decision"), "_error": err}
        raise RuntimeError(f"Tool call error from {tool_name}: {err}")
    return body.get("result", {})


def fetch_trace(client: httpx.Client, gateway: str) -> dict:
    resp = client.get(f"{gateway}/trace", timeout=10)
    resp.raise_for_status()
    return resp.json()


def print_result(step: str, tool: str, result: dict) -> None:
    if result.get("_denied"):
        err = result["_error"]
        data = err.get("data", {})
        decision = result["_decision"]
        print(f"      -> decision: {decision}")
        if data.get("reason"):
            print(f"         reason:   {data['reason']}")
        if data.get("regulation"):
            print(f"         regulation: {data['regulation']}")
    else:
        print(f"      -> decision: {result.get('cmcp_decision', 'allow')}")


# ---------------------------------------------------------------------------
# Main demo flow
# ---------------------------------------------------------------------------

def run(gateway: str, tenant: str) -> None:
    print(f"Connecting to cMCP gateway at {gateway}")
    print(f"Tenant:   {tenant}")
    print(f"Workflow: {WORKFLOW_ID}")
    print()
    print(f"Running the same three tool calls against {tenant}'s policy bundle.")
    print()

    with httpx.Client(headers={"Content-Type": "application/json"}) as client:

        # Call 1: analytics_query — allowed for all tenants.
        print("[1/3] Calling saas.analytics_query ...")
        r1 = make_call(
            client, gateway,
            tool_name="saas.analytics_query",
            arguments={"metric": "daily_active_users", "time_range_days": 30},
            req_id=1,
        )
        print_result("1/3", "saas.analytics_query", r1)

        # Call 2: user_data_export — advisory warn for acme-corp, hard deny for globex-financial.
        print("[2/3] Calling saas.user_data_export ...")
        r2 = make_call(
            client, gateway,
            tool_name="saas.user_data_export",
            arguments={"user_id": "usr_abc123", "format": "json"},
            req_id=2,
        )
        print_result("2/3", "saas.user_data_export", r2)

        # Call 3: config_update — allowed for acme-corp, advisory deny for globex-financial.
        print("[3/3] Calling saas.config_update ...")
        r3 = make_call(
            client, gateway,
            tool_name="saas.config_update",
            arguments={"key": "session_timeout_minutes", "value": "60"},
            req_id=3,
        )
        print_result("3/3", "saas.config_update", r3)

        print()
        print("Fetching TRACE Trust Record from gateway ...")
        try:
            trace = fetch_trace(client, gateway)
            print()
            print("=== TRACE Trust Record ===")
            print(json.dumps(trace, indent=2))
        except Exception as exc:
            print(f"  (Could not fetch live TRACE record: {exc})")
            print(f"  See multi-tenant-saas/trace-output/{tenant}-example.json for reference output.")
            sys.exit(1)

    print()
    print("Done. Start the runtime with the other tenant config to see the policy difference.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SaaS multi-tenant policy isolation demo")
    parser.add_argument(
        "--gateway",
        default=DEFAULT_GATEWAY,
        help=f"cMCP gateway base URL (default: {DEFAULT_GATEWAY})",
    )
    parser.add_argument(
        "--tenant",
        required=True,
        choices=["acme-corp", "globex-financial"],
        help="Which tenant config the runtime was started with",
    )
    args = parser.parse_args()
    run(args.gateway, args.tenant)
