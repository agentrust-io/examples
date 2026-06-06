#!/usr/bin/env python3
"""
Credit risk agent demo for EU private bank.

Calls three MCP tools through the cMCP gateway using raw JSON-RPC 2.0 over HTTP.
No MCP SDK required -- httpx only.

Usage:
    python credit_risk_agent.py [--gateway http://localhost:8443]
"""

import argparse
import json
import sys
import httpx

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_GATEWAY = "http://localhost:8443"

# Realistic fake client data for the demo
CLIENT_ID = "EUR-2024-00847"
DOCUMENT_ID = "BS-2024-Q4"
CREDIT_BUREAU = "equifax"
RISK_SCORE = 72.3
RECOMMENDATION = "approve"
AMOUNT_EUR = 250_000  # Below the 500k escalation threshold


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def make_request(method: str, params: dict, req_id: int) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params,
    }


def call_tool(client: httpx.Client, gateway: str, tool_name: str, arguments: dict, req_id: int) -> dict:
    """Send a tools/call request to the cMCP gateway and return the result."""
    payload = make_request(
        method="tools/call",
        params={"name": tool_name, "arguments": arguments},
        req_id=req_id,
    )
    resp = client.post(f"{gateway}/mcp", json=payload, timeout=30)
    resp.raise_for_status()
    body = resp.json()

    if "error" in body:
        raise RuntimeError(f"Tool call error from {tool_name}: {body['error']}")

    return body.get("result", {})


def fetch_trace(client: httpx.Client, gateway: str) -> dict:
    """Retrieve the TRACE Trust Record for this session."""
    resp = client.get(f"{gateway}/trace", timeout=10)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Main demo flow
# ---------------------------------------------------------------------------

def run(gateway: str) -> None:
    print(f"Connecting to cMCP gateway at {gateway}")
    print(f"Client: {CLIENT_ID}  |  Document: {DOCUMENT_ID}  |  Bureau: {CREDIT_BUREAU}")
    print()

    with httpx.Client(headers={"Content-Type": "application/json"}) as client:

        # Step 1: Read the client's balance sheet from the secure document vault.
        print("[1/3] Calling finance.document_reader ...")
        doc_result = call_tool(
            client, gateway,
            tool_name="finance.document_reader",
            arguments={"document_id": DOCUMENT_ID, "client_id": CLIENT_ID},
            req_id=1,
        )
        print(f"      -> decision: {doc_result.get('cmcp_decision', 'allow')}")

        # Step 2: Retrieve the credit bureau score.
        print("[2/3] Calling finance.credit_score_lookup ...")
        score_result = call_tool(
            client, gateway,
            tool_name="finance.credit_score_lookup",
            arguments={"client_id": CLIENT_ID, "bureau": CREDIT_BUREAU},
            req_id=2,
        )
        print(f"      -> decision: {score_result.get('cmcp_decision', 'allow')}")

        # Step 3: Write the risk assessment back to the core banking system.
        # amount_eur=250000 is below the 500k advisory threshold, so no escalation.
        print("[3/3] Calling finance.risk_report_writer ...")
        report_result = call_tool(
            client, gateway,
            tool_name="finance.risk_report_writer",
            arguments={
                "client_id": CLIENT_ID,
                "risk_score": RISK_SCORE,
                "recommendation": RECOMMENDATION,
                "amount_eur": AMOUNT_EUR,
            },
            req_id=3,
        )
        print(f"      -> decision: {report_result.get('cmcp_decision', 'allow')}")
        print()

        # Fetch and print the TRACE Trust Record for the session.
        print("Fetching TRACE Trust Record from gateway ...")
        try:
            trace = fetch_trace(client, gateway)
            print()
            print("=== TRACE Trust Record ===")
            print(json.dumps(trace, indent=2))
        except Exception as exc:
            print(f"  (Could not fetch live TRACE record: {exc})")
            print("  See financial-services/trace-output/example-trust-record.json for reference output.")

    print()
    print("All tool calls completed. TRACE Trust Record generated.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Credit risk agent demo")
    parser.add_argument(
        "--gateway",
        default=DEFAULT_GATEWAY,
        help=f"cMCP gateway base URL (default: {DEFAULT_GATEWAY})",
    )
    args = parser.parse_args()
    run(args.gateway)
