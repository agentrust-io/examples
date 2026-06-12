#!/usr/bin/env python3
"""
Credit risk agent demo for EU private bank.

Calls three MCP tools through the cMCP Runtime using JSON-RPC 2.0 over HTTP,
then closes the session to obtain the signed TRACE Trust Record.

Usage:
    python credit_risk_agent.py [--gateway http://localhost:8443] [--amount-eur 250000]

The default amount (250,000 EUR) is below the 500k escalation threshold, so
all calls are allowed. Pass --amount-eur 750000 to trigger the MiFID II
human-review deny with structured advice from the Cedar policy.
"""

import argparse
import json
import sys
import httpx

DEFAULT_GATEWAY = "http://localhost:8443"
WORKFLOW_ID = "credit-risk-analyst"

CLIENT_ID = "EUR-2024-00847"
DOCUMENT_ID = "BS-2024-Q4"
CREDIT_BUREAU = "equifax"
RISK_SCORE = 72.3
RECOMMENDATION = "approve"


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
        decision = "advisory_deny" if meta.get("would_have_denied") else "allow"
        print(f"      -> decision: {decision}")
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


def run(gateway: str, amount_eur: int) -> None:
    print(f"Connecting to cMCP Runtime at {gateway}")
    print(f"Client: {CLIENT_ID}  |  Document: {DOCUMENT_ID}  |  Amount: EUR {amount_eur:,}")
    print()

    session_id = None
    with httpx.Client(headers={"Content-Type": "application/json"}) as client:
        print("[1/3] Calling finance.document_reader ...")
        o1 = call_tool(client, gateway, "finance.document_reader",
                       {"document_id": DOCUMENT_ID, "client_id": CLIENT_ID}, 1)
        print_outcome(o1)
        session_id = o1.get("session_id") or session_id

        print("[2/3] Calling finance.credit_score_lookup ...")
        o2 = call_tool(client, gateway, "finance.credit_score_lookup",
                       {"client_id": CLIENT_ID, "bureau": CREDIT_BUREAU}, 2)
        print_outcome(o2)
        session_id = o2.get("session_id") or session_id

        print("[3/3] Calling finance.risk_report_writer ...")
        o3 = call_tool(client, gateway, "finance.risk_report_writer",
                       {"client_id": CLIENT_ID, "risk_score": RISK_SCORE,
                        "recommendation": RECOMMENDATION, "amount_eur": amount_eur}, 3)
        print_outcome(o3)
        session_id = o3.get("session_id") or session_id

        if not o3["ok"]:
            print()
            print("  The risk report was NOT written to the core banking system.")
            print("  Exposures above EUR 500,000 require a human reviewer (MiFID II Art. 25).")

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
    print("Done. Verify the audit chain with:")
    print(f"  curl {gateway}/audit/export?session_id={session_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Credit risk agent demo")
    parser.add_argument("--gateway", default=DEFAULT_GATEWAY,
                        help=f"cMCP Runtime base URL (default: {DEFAULT_GATEWAY})")
    parser.add_argument("--amount-eur", type=int, default=250_000,
                        help="Credit amount in EUR (default 250000; >500000 triggers HITL deny)")
    args = parser.parse_args()
    run(args.gateway, args.amount_eur)
