#!/usr/bin/env python3
"""
Mock SaaS Platform MCP Server for the multi-tenant-saas demo.

Serves the three catalog tools with canned responses on port 8080.
Stdlib only -- no dependencies.

Usage:
    python multi-tenant-saas/server/mock_mcp_server.py
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8080


def _user_data_export(args: dict) -> str:
    return json.dumps({
        "user_id": args.get("user_id", ""),
        "format": args.get("format", "json"),
        "records_exported": 1342,
        "export_id": "EXP-2026-00917",
        "status": "exported",
    })


def _analytics_query(args: dict) -> str:
    return json.dumps({
        "metric": args.get("metric", ""),
        "time_range_days": args.get("time_range_days", 30),
        "value": 48213,
        "trend": "+4.2%",
        "status": "completed",
    })


def _config_update(args: dict) -> str:
    return json.dumps({
        "key": args.get("key", ""),
        "value": args.get("value", ""),
        "previous_value": "30",
        "status": "updated",
    })


TOOLS = {
    "saas.user_data_export": _user_data_export,
    "saas.analytics_query": _analytics_query,
    "saas.config_update": _config_update,
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
        print(f"[mock-saas] {fmt % args}")


if __name__ == "__main__":
    print(f"Mock SaaS Platform MCP Server listening on :{PORT} (tools: {', '.join(TOOLS)})")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
