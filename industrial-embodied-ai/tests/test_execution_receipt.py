from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


EXAMPLE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXAMPLE_DIR))

from controller import IndependentSafetyController  # noqa: E402


def _verify_like_cmcp(receipt: dict, public_key_b64: str, call_id: str) -> None:
    """Reproduce cmcp_verify's external_execution_evidence check: the
    linked_call_id binding, and an Ed25519 signature over the canonical receipt
    with the signature field absent. Raises if the signature does not verify.
    """
    if receipt["linked_call_id"] != call_id:
        raise AssertionError("linked_call_id does not match the entry call_id")
    pad = 4 - (len(public_key_b64) % 4)
    pub = Ed25519PublicKey.from_public_bytes(
        base64.urlsafe_b64decode(public_key_b64 + ("=" * pad if pad != 4 else ""))
    )
    signing_input = json.dumps(
        {k: v for k, v in receipt.items() if k != "signature"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    sig_b64 = receipt["signature"]
    pad = 4 - (len(sig_b64) % 4)
    sig = base64.urlsafe_b64decode(sig_b64 + ("=" * pad if pad != 4 else ""))
    pub.verify(sig, signing_input)


class ExecutionReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = IndependentSafetyController(
            token_key=b"unit-test-only-controller-key"
        )

    def test_receipt_has_required_fields(self) -> None:
        receipt = self.controller.sign_execution_receipt(
            call_id="c1",
            decision={"controller_decision": "rejected", "reason": "human_detected"},
        )
        for field in (
            "issuer",
            "issuer_key_id",
            "signature",
            "evidence_hash",
            "evidence_type",
            "linked_call_id",
        ):
            self.assertIn(field, receipt)
        self.assertTrue(receipt["evidence_hash"].startswith("sha256:"))
        self.assertEqual(receipt["evidence_type"], "controller-execution-receipt/v1")

    def test_receipt_verifies_like_cmcp(self) -> None:
        receipt = self.controller.sign_execution_receipt(
            call_id="c1",
            decision={"controller_decision": "rejected", "reason": "human_detected"},
        )
        # Should not raise.
        _verify_like_cmcp(receipt, self.controller.receipt_public_key_b64, "c1")

    def test_tampered_receipt_fails(self) -> None:
        receipt = self.controller.sign_execution_receipt(
            call_id="c1", decision={"controller_decision": "rejected"}
        )
        receipt["evidence_hash"] = "sha256:" + "cd" * 32  # tamper after signing
        with self.assertRaises(InvalidSignature):
            _verify_like_cmcp(receipt, self.controller.receipt_public_key_b64, "c1")

    def test_linked_call_id_is_bound(self) -> None:
        receipt = self.controller.sign_execution_receipt(
            call_id="c1", decision={"controller_decision": "rejected"}
        )
        with self.assertRaises(AssertionError):
            _verify_like_cmcp(receipt, self.controller.receipt_public_key_b64, "other")

    def test_receipt_key_is_deterministic(self) -> None:
        # Fixed dev seed: the receipt key id is reproducible across instances,
        # so committed evidence stays stable.
        other = IndependentSafetyController(token_key=b"different-token-key")
        self.assertEqual(self.controller.receipt_key_id, other.receipt_key_id)


if __name__ == "__main__":
    unittest.main()
