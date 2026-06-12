#!/usr/bin/env python3
"""
Mock EU Credit Risk MCP Server for the financial-services demo.

Serves the three catalog tools with canned responses on port 8080.
Stdlib only -- no dependencies.

Usage:
    python financial-services/server/mock_mcp_server.py
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8080


def _document_reader(args: dict) -> str:
    return json.dumps({
        "document_id": args.get("document_id", ""),
        "client_id": args.get("client_id", ""),
        "document_type": "balance_sheet",
        "period": "2024-Q4",
        "total_assets_eur": 4_820_000,
        "total_liabilities_eur": 3_140_000,
        "status": "retrieved",
    })


def _credit_score_lookup(args: dict) -> str:
    return json.dumps({
        "client_id": args.get("client_id", ""),
        "bureau": args.get("bureau", "equifax"),
        "score": 742,
        "scale": "280-850",
        "retrieved_at": "2026-06-10T09:00:00Z",
    })


def _risk_report_writer(args: dict) -> str:
    return json.dumps({
        "client_id": args.get("client_id", ""),
        "risk_score": args.get("risk_score"),
        "recommendation": args.get("recommendation"),
        "amount_eur": args.get("amount_eur"),
        "report_id": "RR-2026-04471",
        "status": "written",
    })


TOOLS = {
    "finance.document_reader": _document_reader,
    "finance.credit_score_lookup": _credit_score_lookup,
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
