# Agentic Commerce Accountability

This runnable example asks whether an auditor can connect a completed purchase
to the authority the user granted, the exact request evaluated by policy, and
the runtime evidence for that decision.

The bundle links a constrained authority grant, a UCP-shaped checkout request,
an AGT-style policy decision, a TRACE evidence reference, and a merchant receipt
with canonical SHA-256 digests. The valid fixture stays below a delegated USD
200 limit. The tampered fixture changes the purchase to USD 500 after the policy
decision, so verification detects the overspend and broken digest link.

```bash
python generate_fixtures.py
python -m unittest discover -s tests -v
python verify_purchase.py fixtures/valid-purchase.json
python verify_purchase.py fixtures/overspend-tamper.json
```

## Security boundary

This is a deterministic composition example, not a claim of UCP, AGT, cA2A, or
TRACE conformance. It verifies constraints and cross-artifact bindings. It does
not verify signatures, merchant settlement, hardware quotes, revocation, or a
live transparency-log receipt. Production use should replace each illustrative
artifact with the corresponding protocol's signed, independently verifiable
record.
