#!/usr/bin/env python3
"""
Clinical decision support agent demo for hospital AI compliance.

Calls three EHR tools through the cMCP Runtime using JSON-RPC 2.0 over HTTP,
then closes the session to obtain the signed TRACE Trust Record.

Usage:
    python clinical_decision_agent.py [--gateway http://localhost:8443] [--trigger-hitl]

Without --trigger-hitl: patient_risk_category=standard, all tool calls allowed.
With    --trigger-hitl: patient_risk_category=high, the treatment plan write is
                         denied with EU AI Act Art. 14 advice from the Cedar policy.
"""

import argparse
import json
import sys
import httpx

DEFAULT_GATEWAY = "http://localhost:8443"
WORKFLOW_ID = "clinical-decision-support"

PATIENT_ID = "P-2024-008471"
SYMPTOMS = ["fatigue", "polyuria", "polydipsia", "blurred vision"]
LAB_VALUES = {"fasting_glucose_mmol": 9.2, "hba1c_percent": 8.1, "bmi": 31.4}
DIAGNOSIS = "Type 2 Diabetes Mellitus with Hypertension"
TREATMENT = "Metformin 500mg twice daily; lisinopril 10mg once daily; HbA1c recheck in 3 months"


def call_tool(client: httpx.Client, gateway: str, tool_name: str, arguments: dict, req_id: int) -> dict:
    """POST a tools/call. Returns {"ok": bool, "result"/"error", "session_id"}."""
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


def run(gateway: str, trigger_hitl: bool) -> None:
    risk_category = "high" if trigger_hitl else "standard"
    print(f"Connecting to cMCP Runtime at {gateway}")
    print(f"Patient: {PATIENT_ID}  |  Risk category: {risk_category}")
    if trigger_hitl:
        print("Mode: --trigger-hitl — the treatment plan write will require HITL approval")
    print()

    session_id = None
    with httpx.Client(headers={"Content-Type": "application/json"}) as client:
        print("[1/3] Calling ehr.patient_record_lookup ...")
        o1 = call_tool(client, gateway, "ehr.patient_record_lookup",
                       {"patient_id": PATIENT_ID, "record_type": "full"}, 1)
        print_outcome(o1)
        session_id = o1.get("session_id") or session_id

        print("[2/3] Calling ehr.clinical_decision_support ...")
        o2 = call_tool(client, gateway, "ehr.clinical_decision_support",
                       {"patient_id": PATIENT_ID, "presenting_symptoms": SYMPTOMS,
                        "lab_values": LAB_VALUES}, 2)
        print_outcome(o2)
        session_id = o2.get("session_id") or session_id

        print("[3/3] Calling ehr.treatment_plan_writer ...")
        o3 = call_tool(client, gateway, "ehr.treatment_plan_writer",
                       {"patient_id": PATIENT_ID, "diagnosis": DIAGNOSIS,
                        "treatment": TREATMENT,
                        "patient_risk_category": risk_category}, 3)
        print_outcome(o3)
        session_id = o3.get("session_id") or session_id

        if not o3["ok"]:
            print()
            print("  The treatment plan was NOT written to the EHR.")
            print("  An attending physician must review and approve before the plan takes effect.")
            print("  The audit chain records this deny for EU AI Act Art. 14 evidence.")

        print()
        if session_id is None:
            print("No session id received — cannot fetch TRACE Trust Record.")
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
    parser = argparse.ArgumentParser(description="Clinical decision support agent demo")
    parser.add_argument("--gateway", default=DEFAULT_GATEWAY,
                        help=f"cMCP Runtime base URL (default: {DEFAULT_GATEWAY})")
    parser.add_argument("--trigger-hitl", action="store_true",
                        help="Set patient_risk_category=high to trigger the EU AI Act Art. 14 HITL deny")
    args = parser.parse_args()
    run(args.gateway, args.trigger_hitl)
