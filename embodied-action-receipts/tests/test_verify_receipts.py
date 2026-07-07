from __future__ import annotations

import json
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from verify_receipts import verify_fixture  # noqa: E402


class ReceiptFixtureTests(unittest.TestCase):
    def test_fixtures_match_expected_results(self) -> None:
        for path in sorted((ROOT / "fixtures").glob("*.json")):
            with self.subTest(path=path.name):
                fixture = json.loads(path.read_text())
                self.assertEqual(verify_fixture(path), fixture["expected"])

    def test_rejected_receipt_is_valid_evidence(self) -> None:
        result = verify_fixture(ROOT / "fixtures" / "controller-rejected.json")
        self.assertEqual(result, {"result": "valid", "receipt_state": "rejected"})


if __name__ == "__main__":
    unittest.main()

