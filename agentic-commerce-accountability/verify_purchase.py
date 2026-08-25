#!/usr/bin/env python3
"""Offline verifier for the agentic-commerce accountability example."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def verify(bundle: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    grant = bundle["authority_grant"]
    request = bundle["purchase_request"]
    decision = bundle["policy_decision"]
    evidence = bundle["runtime_evidence"]
    receipt = bundle["purchase_receipt"]
    if request["operation"] not in grant["allowed_operations"]:
        errors.append("operation is outside delegated authority")
    if request["currency"] != grant["currency"]:
        errors.append("currency differs from delegated authority")
    if request["merchant_id"] not in grant["allowed_merchants"]:
        errors.append("merchant is outside delegated authority")
    if request["amount_minor"] > grant["max_amount_minor"]:
        errors.append("amount exceeds delegated authority")
    if decision["request_digest"] != digest(request):
        errors.append("policy decision is not bound to the purchase request")
    if decision["authority_digest"] != digest(grant):
        errors.append("policy decision is not bound to the authority grant")
    if evidence["policy_decision_digest"] != digest(decision):
        errors.append("runtime evidence is not bound to the policy decision")
    if receipt["request_digest"] != digest(request):
        errors.append("receipt is not bound to the purchase request")
    if receipt["runtime_evidence_digest"] != digest(evidence):
        errors.append("receipt is not bound to the runtime evidence")
    if decision["outcome"] != "allow":
        errors.append("policy decision did not allow the purchase")
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python verify_purchase.py <bundle.json>", file=sys.stderr)
        return 2
    bundle = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    errors = verify(bundle)
    if errors:
        print("REJECTED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("ACCEPTED: authority, decision, runtime evidence, and receipt are linked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
