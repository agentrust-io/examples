#!/usr/bin/env python3
"""
Mock EU Credit Risk MCP Server for the financial-services demo.

Serves the six catalog tools on port 8080. Tool responses are computed by
``credit_engine`` from a small set of realistic EU corporate client fixtures,
so the server, the tests and the agent all agree on the same data.

Stdlib only -- no dependencies.

Usage:
    python financial-services/server/mock_mcp_server.py
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

EXAMPLE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLE_DIR))

import credit_engine  # noqa: E402

PORT = 8080


def _document_reader(args: dict) -> str:
    return json.dumps(credit_engine.read_financials(args.get("client_id", credit_engine.DEFAULT_CLIENT)))


def _sanctions_screening(args: dict) -> str:
    return json.dumps(credit_engine.screen_sanctions(args.get("client_id", credit_engine.DEFAULT_CLIENT)))


def _credit_bureau_lookup(args: dict) -> str:
    return json.dumps(credit_engine.bureau_report(
        args.get("client_id", credit_engine.DEFAULT_CLIENT),
        args.get("bureau", "creditreform"),
    ))


def _exposure_aggregation(args: dict) -> str:
    return json.dumps(credit_engine.aggregate_exposure(
        args.get("client_id", credit_engine.DEFAULT_CLIENT),
        int(args.get("proposed_facility_eur", 0)),
    ))


def _risk_model(args: dict) -> str:
    return json.dumps(credit_engine.run_risk_model(
        args.get("client_id", credit_engine.DEFAULT_CLIENT),
        int(args.get("proposed_facility_eur", 0)),
    ))


def _risk_report_writer(args: dict) -> str:
    return json.dumps({
        "client_id": args.get("client_id", ""),
        "internal_rating": args.get("internal_rating"),
        "recommendation": args.get("recommendation"),
        "amount_eur": args.get("amount_eur"),
        "report_id": "RR-2026-04471",
        "status": "written",
    })


TOOLS = {
    "finance.document_reader": _document_reader,
    "finance.sanctions_screening": _sanctions_screening,
    "finance.credit_bureau_lookup": _credit_bureau_lookup,
    "finance.exposure_aggregation": _exposure_aggregation,
    "finance.risk_model": _risk_model,
    "finance.risk_report_writer": _risk_report_writer,
}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        if self.path != "/mcp":
            self._reply(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        request = json.loads(self.rfile.read(length))
        params = request.get("params", {})
        tool = params.get("name", "")
        handler = TOOLS.get(tool)
        if handler is None:
            self._reply(200, {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {"code": -32601, "message": f"unknown tool: {tool}"},
            })
            return
        text = handler(params.get("arguments", {}))
        self._reply(200, {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": {"content": [{"type": "text", "text": text}]},
        })

    def _reply(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print(f"[mock-mcp] {fmt % args}")


if __name__ == "__main__":
    print(f"Mock EU Credit Risk MCP Server listening on :{PORT} (tools: {', '.join(TOOLS)})")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
