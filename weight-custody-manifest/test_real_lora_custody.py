import base64
import pathlib

import pytest
from cryptography.exceptions import InvalidTag

from real_lora_custody import decrypt_artifact, encrypt_artifact


def _adapter(path: pathlib.Path) -> pathlib.Path:
    path.mkdir()
    (path / "adapter_config.json").write_text('{"peft_type":"LORA"}', encoding="utf-8")
    (path / "adapter_model.safetensors").write_bytes(b"real-saved-adapter-placeholder")
    return path


def test_encrypted_adapter_round_trip(tmp_path: pathlib.Path) -> None:
    source = _adapter(tmp_path / "source")
    key = bytes(range(32))
    envelope = encrypt_artifact(source, key)
    observed = decrypt_artifact(envelope, key, tmp_path / "verified")
    assert observed == envelope["artifact_digest"]
    assert (tmp_path / "verified" / "adapter_model.safetensors").read_bytes() == (
        b"real-saved-adapter-placeholder"
    )


def test_ciphertext_tamper_is_refused(tmp_path: pathlib.Path) -> None:
    envelope = encrypt_artifact(_adapter(tmp_path / "source"), bytes(32))
    ciphertext = bytearray(base64.b64decode(envelope["ciphertext_b64"]))
    ciphertext[0] ^= 1
    envelope["ciphertext_b64"] = base64.b64encode(ciphertext).decode()
    with pytest.raises(InvalidTag):
        decrypt_artifact(envelope, bytes(32), tmp_path / "refused")


def test_manifest_digest_substitution_is_refused(tmp_path: pathlib.Path) -> None:
    envelope = encrypt_artifact(_adapter(tmp_path / "source"), bytes(32))
    envelope["artifact_digest"] = "sha256:" + "0" * 64
    with pytest.raises(InvalidTag):
        decrypt_artifact(envelope, bytes(32), tmp_path / "refused")
