from __future__ import annotations
import json
import sys
import unittest
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLE))
from generate_fixtures import build  # noqa: E402
from verify_purchase import verify  # noqa: E402


class PurchaseVerificationTests(unittest.TestCase):
    def test_valid_purchase_is_accepted(self) -> None:
        self.assertEqual(verify(build()), [])

    def test_overspend_and_stale_link_are_rejected(self) -> None:
        bundle = build()
        bundle["purchase_request"]["amount_minor"] = 50_000
        errors = verify(bundle)
        self.assertIn("amount exceeds delegated authority", errors)
        self.assertIn("policy decision is not bound to the purchase request", errors)

    def test_merchant_substitution_is_rejected(self) -> None:
        bundle = build()
        bundle["purchase_request"]["merchant_id"] = "merchant:attacker"
        self.assertIn("merchant is outside delegated authority", verify(bundle))

    def test_committed_fixture_matches_generator(self) -> None:
        committed = json.loads((EXAMPLE / "fixtures" / "valid-purchase.json").read_text())
        self.assertEqual(committed, build())


if __name__ == "__main__":
    unittest.main()
