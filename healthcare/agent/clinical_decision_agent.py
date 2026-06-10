#!/usr/bin/env python3
"""
Clinical decision support agent demo for hospital AI compliance.

Calls three EHR tools through the cMCP gateway using raw JSON-RPC 2.0 over HTTP.
No MCP SDK required -- httpx only.

Usage:
    python clinical_decision_agent.py [--gateway http://localhost:8443] [--trigger-hitl]

Without --trigger-hitl: patient_risk_category=standard, all tool calls allowed.
With    --trigger-hitl: patient_risk_category=high, treatment plan write is
                         blocked with an EU AI Act Art. 14 HITL advisory.
"""

import argparse
import json
import sys
import httpx

DEFAULT_GATEWAY = "http://localhost:8443"

# Realistic demo patient
PATIENT_ID = "P-2024-008471"
SYMPTOMS = ["fatigue", "polyuria", "polydipsia", "blurred vision"]
LAB_VALUES = {"fasting_glucose_mmol": 9.2, "hba1c_percent": 8.1, "bmi": 31.4}
DIAGNOSIS = "Type 2 Diabetes Mellitus with Hypertension"
TREATMENT = "Metformin 500mg twice daily; lisinopril 10mg once daily; HbA1c recheck in 3 months"


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def make_call(client: httpx.Client, gateway: str, tool_name: str, arguments: dict, req_id: int) -> dict:
    """Send a tools/call to the cMCP gateway and return the full result dict."""
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
        # Structured error: advisory_deny returns an error but has HITL advice in data
        if isinstance(err.get("data"), dict) and err["data"].get("decision") in ("advisory_deny", "deny"):
            return {"_denied": True, "_error": err}
        raise RuntimeError(f"Tool call error from {tool_name}: {err}")
    return body.get("result", {})


def fetch_trace(client: httpx.Client, gateway: str) -> dict:
    resp = client.get(f"{gateway}/trace", timeout=10)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Main demo flow
# ---------------------------------------------------------------------------

def run(gateway: str, trigger_hitl: bool) -> None:
    risk_category = "high" if trigger_hitl else "standard"

    print(f"Connecting to cMCP gateway at {gateway}")
    print(f"Patient: {PATIENT_ID}  |  Risk category: {risk_category}")
    if trigger_hitl:
        print("Mode: --trigger-hitl enabled — treatment plan write will require HITL approval")
    print()

    with httpx.Client(headers={"Content-Type": "application/json"}) as client:

        # Step 1: Look up the patient record.
        print("[1/3] Calling ehr.patient_record_lookup ...")
        rec_result = make_call(
            client, gateway,
            tool_name="ehr.patient_record_lookup",
            arguments={"patient_id": PATIENT_ID, "record_type": "full"},
            req_id=1,
        )
        print(f"      -> decision: {rec_result.get('cmcp_decision', 'allow')}")

        # Step 2: Run the AI differential diagnosis.
        print("[2/3] Calling ehr.clinical_decision_support ...")
        cds_result = make_call(
            client, gateway,
            tool_name="ehr.clinical_decision_support",
            arguments={
                "patient_id": PATIENT_ID,
                "presenting_symptoms": SYMPTOMS,
                "lab_values": LAB_VALUES,
            },
            req_id=2,
        )
        print(f"      -> decision: {cds_result.get('cmcp_decision', 'allow')}")

        # Step 3: Write the treatment plan.
        # When patient_risk_category == "high", Cedar Rule 2 fires and the gateway
        # returns an advisory_deny with EU AI Act Art. 14 HITL advice.
        print("[3/3] Calling ehr.treatment_plan_writer ...")
        plan_result = make_call(
            client, gateway,
            tool_name="ehr.treatment_plan_writer",
            arguments={
                "patient_id": PATIENT_ID,
                "diagnosis": DIAGNOSIS,
                "treatment": TREATMENT,
                "patient_risk_category": risk_category,
            },
            req_id=3,
        )

        if plan_result.get("_denied"):
            err = plan_result["_error"]
            data = err.get("data", {})
            print(f"      -> decision: {data.get('decision', 'deny')}")
            print()
            print("  HITL advisory payload:")
            print(f"    reason:        {data.get('reason', '')}")
            print(f"    regulation:    {data.get('regulation', '')}")
            print(f"    reviewer_role: {data.get('reviewer_role', '')}")
            print()
            print("  The treatment plan was NOT written to the EHR.")
            print("  An attending physician must review and approve before the plan takes effect.")
            print("  The TRACE Trust Record records this as an advisory_deny for EU AI Act audit purposes.")
        else:
            print(f"      -> decision: {plan_result.get('cmcp_decision', 'allow')}")

        print()

        # Fetch TRACE Trust Record.
        print("Fetching TRACE Trust Record from gateway ...")
        try:
            trace = fetch_trace(client, gateway)
            print()
            print("=== TRACE Trust Record ===")
            print(json.dumps(trace, indent=2))
        except Exception as exc:
            print(f"  (Could not fetch live TRACE record: {exc})")
            print("  See healthcare/trace-output/ for reference output.")
            sys.exit(1)

    print()
    print("All tool calls completed. TRACE Trust Record generated.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clinical decision support agent demo")
    parser.add_argument(
        "--gateway",
        default=DEFAULT_GATEWAY,
        help=f"cMCP gateway base URL (default: {DEFAULT_GATEWAY})",
    )
    parser.add_argument(
        "--trigger-hitl",
        action="store_true",
        help="Set patient_risk_category=high to trigger the EU AI Act Art. 14 HITL advisory",
    )
    args = parser.parse_args()
    run(args.gateway, args.trigger_hitl)
