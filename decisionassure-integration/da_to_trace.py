#!/usr/bin/env python3
"""
DecisionAssure -> TRACE Claim Adapter
Converts a DecisionAssure signed trace (JSON) into a TRACE-compatible
EAT/JWT claim that can be submitted to the trace-registry.
Part of the agentrust-io examples repository.
"""

import json
import hashlib
import base64
from datetime import datetime, timezone
from typing import Dict, Any, Optional

def compute_continuity_analysis(trace: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract continuity failures, governance score, and collusion suspicion.
    """
    steps = trace.get('steps', trace.get('execution_trace', []))
    failures = []
    continuity_valid_all = True
    for i, step in enumerate(steps, 1):
        continuity = step.get('continuity_valid', True)
        if not continuity:
            continuity_valid_all = False
            failures.append({
                "step_index": step.get('step_index', i),
                "reason": step.get('reason', ""),
                "diff": step.get('reference_frame_diff', {}),
                "hidden_commitment": step.get('hidden_commitment', False),
                "evidence_fresh": step.get('evidence_fresh', True),
                "rollback_viable": step.get('rollback_viable', True)
            })
    # Governance score might be at top-level or computed
    gov_score = trace.get('governance_score')
    # Collusion suspicion score – optional, could be in top-level or first step
    collusion_score = trace.get('collusion_suspicion_score')
    return {
        "continuity_failures": failures,
        "continuity_persisted": trace.get('causal_continuity_persisted', continuity_valid_all),
        "governance_score": gov_score,
        "collusion_suspicion_score": collusion_score,
        "integrity_status": trace.get('integrity_status', 'UNKNOWN')
    }

def create_trace_claim(trace_file: str) -> str:
    """
    Reads a DecisionAssure trace file, canonicalises it,
    computes a hash, builds a TRACE claim (EAT/JWT-like), and returns
    a URL-safe base64 encoded token.
    """
    with open(trace_file, 'r') as f:
        trace = json.load(f)

    # 1. Canonicalise the trace for hashing
    canonical_trace = json.dumps(trace, sort_keys=True, separators=(',', ':'))
    trace_hash = hashlib.sha256(canonical_trace.encode()).hexdigest()

    # 2. Analyse continuity and collusion
    analysis = compute_continuity_analysis(trace)

    # 3. Build TRACE claim – minimal EAT claims set
    #    (based on draft of trace-spec)
    claim = {
        "eat_profile": "https://agentrust.io/trace/v1",
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "sub": "decisionassure-verifier",
        "detection_layer": {
            "tool": "DecisionAssure",
            "version": "2.0",
            "analysis": analysis
        },
        "trace_hash": trace_hash,
        "claim_type": "runtime_anomaly_detection"
    }

    # 4. Encode as JWT-like (without signature for demo; in production you'd sign)
    claim_json = json.dumps(claim, sort_keys=True)
    encoded = base64.urlsafe_b64encode(claim_json.encode()).decode().rstrip('=')
    return encoded

def main():
    import sys
    if len(sys.argv) != 2:
        print("Usage: python da_to_trace.py <decisionassure_trace_signed.json>")
        sys.exit(1)
    token = create_trace_claim(sys.argv[1])
    print(f"TRACE claim (mock): {token}")
    # Optionally, you could also submit to a local trace-registry endpoint.

if __name__ == "__main__":
    main()