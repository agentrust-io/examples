#!/usr/bin/env python3
"""
SaaS platform agent demo showing per-tenant Cedar policy isolation.

Runs the same three tool calls; the outcome depends on which tenant's policy
bundle the runtime was started with:

    acme-corp        (advisory): analytics allow, user_data_export
                     advisory_deny with GDPR advice (logged, not blocked),
                     config_update allow
    globex-financial (enforcing): analytics allow, user_data_export deny,
                     config_update deny -- both with structured advice

Usage:
    python saas_agent.py --tenant acme-corp|globex-financial [--gateway http://localhost:8443]
"""

import argparse
import json
import sys
import httpx

DEFAULT_GATEWAY = "http://localhost:8443"
WORKFLOW_ID = "analytics-workflow"


def call_tool(client: httpx.Client, gateway: str, tool_name: str, arguments: dict, req_id: int) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
            "_cmcp": {"workflow_id": WORKFLOW_ID},
        },
    }
    resp = client.post(f"{gateway}/mcp", json=payload, timeout=30)
    body = resp.json()
    if "error" in body:
        return {"ok": False, "error": body["error"], "session_id": None}
    result = body["result"]
    return {
        "ok": True,
        "result": result,
        "session_id": result.get("_cmcp", {}).get("session_id"),
    }


def print_outcome(outcome: dict) -> None:
    if outcome["ok"]:
        meta = outcome["result"].get("_cmcp", {})
        if meta.get("would_have_denied"):
            print("      -> decision: advisory_deny (logged, not blocked)")
            advice = meta.get("advice")
            if advice:
                print("         advice from policy:")
                for key, value in advice.items():
                    print(f"           {key}: {value}")
        else:
            print("      -> decision: allow")
    else:
        data = outcome["error"].get("data", {})
        print(f"      -> decision: deny ({data.get('error_code', 'unknown')})")
        advice = data.get("advice")
        if advice:
            print("         advice from policy:")
            for key, value in advice.items():
                print(f"           {key}: {value}")


def close_session(client: httpx.Client, gateway: str, session_id: str) -> dict:
    resp = client.post(f"{gateway}/sessions/{session_id}/close", timeout=10)
    resp.raise_for_status()
    return resp.json()


def run(gateway: str, tenant: str) -> None:
    print(f"Connecting to cMCP Runtime at {gateway}")
    print(f"Tenant:   {tenant}")
    print(f"Workflow: {WORKFLOW_ID}")
    print()
    print(f"Running the same three tool calls against {tenant}'s policy bundle.")
    print()

    session_id = None
    with httpx.Client(headers={"Content-Type": "application/json"}) as client:
        print("[1/3] Calling saas.analytics_query ...")
        o1 = call_tool(client, gateway, "saas.analytics_query",
                       {"metric": "daily_active_users", "time_range_days": 30}, 1)
        print_outcome(o1)
        session_id = o1.get("session_id") or session_id

        print("[2/3] Calling saas.user_data_export ...")
        o2 = call_tool(client, gateway, "saas.user_data_export",
                       {"user_id": "usr_abc123", "format": "json"}, 2)
        print_outcome(o2)
        session_id = o2.get("session_id") or session_id

        print("[3/3] Calling saas.config_update ...")
        o3 = call_tool(client, gateway, "saas.config_update",
                       {"key": "session_timeout_minutes", "value": "60"}, 3)
        print_outcome(o3)
        session_id = o3.get("session_id") or session_id

        print()
        if session_id is None:
            print("No session id received - cannot fetch TRACE Trust Record.")
            sys.exit(1)

        print(f"Closing session {session_id} and fetching the signed TRACE Trust Record ...")
        claim = close_session(client, gateway, session_id)
        print()
        print("=== TRACE Trust Record (signed RuntimeClaim) ===")
        print(json.dumps(claim, indent=2))

    print()
    print("Done. Restart the runtime with the other tenant config to see the policy difference.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SaaS multi-tenant policy isolation demo")
    parser.add_argument("--gateway", default=DEFAULT_GATEWAY,
                        help=f"cMCP Runtime base URL (default: {DEFAULT_GATEWAY})")
    parser.add_argument("--tenant", required=True,
                        choices=["acme-corp", "globex-financial"],
                        help="Which tenant config the runtime was started with")
    args = parser.parse_args()
    run(args.gateway, args.tenant)
