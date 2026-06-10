#!/usr/bin/env python3
"""Minimal echo agent for the cMCP startup quickstart.

Calls test.echo through the gateway and prints the TRACE Trust Record.

Usage:
    python echo_agent.py [--gateway http://localhost:8443]
"""

import argparse
import json
import sys
import httpx

DEFAULT_GATEWAY = "http://localhost:8443"


def call_tool(client: httpx.Client, gateway: str, tool_name: str, arguments: dict, req_id: int) -> dict:
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
        raise RuntimeError(f"Tool call error: {body['error']}")
    return body.get("result", {})


def fetch_trace(client: httpx.Client, gateway: str) -> dict:
    resp = client.get(f"{gateway}/trace", timeout=10)
    resp.raise_for_status()
    return resp.json()


def run(gateway: str) -> None:
    print(f"Connecting to cMCP gateway at {gateway}")
    print()

    with httpx.Client(headers={"Content-Type": "application/json"}) as client:
        print("[1/1] Calling test.echo ...")
        result = call_tool(client, gateway, "test.echo", {"message": "hello from cMCP"}, 1)
        decision = result.get("cmcp_decision", "allow")
        echoed = ""
        content = result.get("content", [])
        if content:
            echoed = content[0].get("text", "")
        print(f"      -> decision: {decision}")
        if echoed:
            print(f"      -> echoed:   {echoed}")
        print()

        print("Fetching TRACE Trust Record ...")
        try:
            trace = fetch_trace(client, gateway)
            print()
            print("=== TRACE Trust Record ===")
            print(json.dumps(trace, indent=2))
        except Exception as exc:
            print(f"  (Could not fetch live TRACE record: {exc})")
            print("  Start the runtime first: CMCP_DEV_MODE=1 cmcp start --config startup-tpm/cmcp-config.yaml")
            sys.exit(1)

    print()
    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="cMCP echo agent quickstart")
    parser.add_argument(
        "--gateway",
        default=DEFAULT_GATEWAY,
        help=f"cMCP gateway base URL (default: {DEFAULT_GATEWAY})",
    )
    args = parser.parse_args()
    run(args.gateway)
