"""Offline verifier for embodied-action receipt fixtures."""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


ROOT = Path(__file__).parent


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def sha256_ref(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def action_preimage(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent_id": action["agent_id"],
        "action_type": action["action_type"],
        "action_scope": action["action_scope"],
        "action_timestamp": action["action_timestamp"],
    }


def receipt_preimage(receipt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in receipt.items() if k != "signature"}


def receipt_hash(receipt: dict[str, Any]) -> str:
    return sha256_ref(receipt)


def load_trusted_keys(path: Path = ROOT / "trusted-keys.json") -> dict[str, Ed25519PublicKey]:
    data = json.loads(path.read_text())
    keys = {}
    for key_id, key in data["controller_signers"].items():
        keys[key_id] = Ed25519PublicKey.from_public_bytes(b64url_decode(key["public_key_b64url"]))
    return keys


def verify_fixture(path: Path, trusted_keys: dict[str, Ed25519PublicKey] | None = None) -> dict[str, Any]:
    fixture = json.loads(path.read_text())
    trusted_keys = trusted_keys or load_trusted_keys()

    trace = fixture["trace"]
    action = fixture["action"]
    receipts = fixture.get("receipts", [])
    expected_required = trace.get("verification", {}).get("action_receipts") == "required"

    recomputed_action_ref = sha256_ref(action_preimage(action))
    if recomputed_action_ref != action.get("action_ref"):
        return {"result": "invalid", "receipt_state": "action_ref_mismatch"}

    if expected_required and not receipts:
        return {"result": "invalid", "receipt_state": "missing"}

    previous_hash = None
    final_state = "absent"
    final_verdict = None

    for receipt in sorted(receipts, key=lambda r: r["sequence"]):
        if receipt["call_id"] != trace["cmcp_call_id"]:
            return {"result": "invalid", "receipt_state": "call_id_mismatch"}
        if receipt["trace_id"] != trace["trace_id"]:
            return {"result": "invalid", "receipt_state": "trace_id_mismatch"}
        if receipt["action_ref"] != action["action_ref"]:
            return {"result": "invalid", "receipt_state": "action_ref_mismatch"}
        if receipt.get("prev_receipt_hash") != previous_hash:
            return {"result": "invalid", "receipt_state": "chain_mismatch"}

        key = trusted_keys.get(receipt["issuer_key_id"])
        if key is None:
            return {"result": "invalid", "receipt_state": "untrusted"}

        signature = receipt["signature"]
        if not signature.startswith("ed25519:"):
            return {"result": "invalid", "receipt_state": "signature_format"}

        try:
            key.verify(b64url_decode(signature.removeprefix("ed25519:")), canonical_bytes(receipt_preimage(receipt)))
        except InvalidSignature:
            return {"result": "invalid", "receipt_state": "invalid_signature"}

        previous_hash = receipt_hash(receipt)
        final_verdict = receipt["verdict"]
        final_state = receipt["terminal_state"]

    if final_verdict == "rejected" or final_state.endswith("rejected"):
        return {"result": "valid", "receipt_state": "rejected"}
    if final_verdict == "accepted":
        return {"result": "valid", "receipt_state": "accepted"}
    return {"result": "valid", "receipt_state": final_state}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python verify_receipts.py <fixture.json>", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    result = verify_fixture(path)
    print(json.dumps(result, indent=2, sort_keys=True))

    expected = json.loads(path.read_text()).get("expected")
    if expected and result != expected:
        print(f"expected {expected}, got {result}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

