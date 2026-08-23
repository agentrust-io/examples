from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from generate_fixtures import sign
from verify_receipts import (
    load_trusted_keys,
    receipt_hash,
    verify_fixture,
)


class ReceiptFixtureTests(unittest.TestCase):
    def test_fixtures_match_expected_results(self) -> None:
        for path in sorted((ROOT / "fixtures").glob("*.json")):
            with self.subTest(path=path.name):
                fixture = json.loads(path.read_text())
                self.assertEqual(verify_fixture(path), fixture["expected"])

    def test_rejected_receipt_is_valid_evidence(self) -> None:
        result = verify_fixture(ROOT / "fixtures" / "controller-rejected.json")
        self.assertEqual(result, {"result": "valid", "receipt_state": "rejected"})

    def test_explicit_empty_trust_store_trusts_nobody(self) -> None:
        result = verify_fixture(ROOT / "fixtures" / "valid-chain.json", trusted_keys={})
        self.assertEqual(result, {"result": "invalid", "receipt_state": "untrusted"})

    def test_trusted_key_cannot_claim_a_different_issuer(self) -> None:
        fixture = json.loads((ROOT / "fixtures" / "valid-chain.json").read_text())
        forged = deepcopy(fixture["receipts"][0])
        forged.pop("signature")
        forged["issuer"] = "spiffe://attacker.example/controller"
        fixture["receipts"] = [sign(forged)]
        path = ROOT / "fixtures" / ".test-wrong-issuer.json"
        try:
            path.write_text(json.dumps(fixture))
            result = verify_fixture(path, trusted_keys=load_trusted_keys())
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result, {"result": "invalid", "receipt_state": "issuer_mismatch"})

    def test_receipt_sequences_must_be_contiguous(self) -> None:
        fixture = json.loads((ROOT / "fixtures" / "valid-chain.json").read_text())
        first = fixture["receipts"][0]
        second = deepcopy(fixture["receipts"][1])
        second.pop("signature")
        second["sequence"] = 3
        second["prev_receipt_hash"] = receipt_hash(first)
        fixture["receipts"][1] = sign(second)
        path = ROOT / "fixtures" / ".test-sequence-gap.json"
        try:
            path.write_text(json.dumps(fixture))
            result = verify_fixture(path)
        finally:
            path.unlink(missing_ok=True)
        self.assertEqual(result, {"result": "invalid", "receipt_state": "sequence_mismatch"})


if __name__ == "__main__":
    unittest.main()

