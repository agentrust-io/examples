#!/usr/bin/env python3
"""
Mock Hospital EHR MCP Server for the healthcare demo.

Serves the three catalog tools with canned responses on port 8080.
Stdlib only -- no dependencies.

Usage:
    python healthcare/server/mock_mcp_server.py
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8080


def _patient_record_lookup(args: dict) -> str:
    return json.dumps({
        "patient_id": args.get("patient_id", ""),
        "record_type": args.get("record_type", "full"),
        "age": 54,
        "active_diagnoses": ["essential hypertension"],
        "current_medications": ["lisinopril 10mg"],
        "last_visit": "2026-05-28",
        "status": "retrieved",
    })


def _clinical_decision_support(args: dict) -> str:
    return json.dumps({
        "patient_id": args.get("patient_id", ""),
        "differential": [
            {"condition": "Type 2 Diabetes Mellitus", "confidence": 0.91},
            {"condition": "Metabolic Syndrome", "confidence": 0.64},
        ],
        "recommended_tests": ["oral glucose tolerance test", "lipid panel"],
        "status": "completed",
    })


def _treatment_plan_writer(args: dict) -> str:
    return json.dumps({
        "patient_id": args.get("patient_id", ""),
        "diagnosis": args.get("diagnosis"),
        "treatment": args.get("treatment"),
        "patient_risk_category": args.get("patient_risk_category"),
        "plan_id": "TP-2026-08831",
        "status": "written",
    })


TOOLS = {
    "ehr.patient_record_lookup": _patient_record_lookup,
    "ehr.clinical_decision_support": _clinical_decision_support,
    "ehr.treatment_plan_writer": _treatment_plan_writer,
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
        print(f"[mock-ehr] {fmt % args}")


if __name__ == "__main__":
    print(f"Mock Hospital EHR MCP Server listening on :{PORT} (tools: {', '.join(TOOLS)})")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
