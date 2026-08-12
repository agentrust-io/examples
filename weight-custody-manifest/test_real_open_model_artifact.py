"""Offline checks for deterministic complete-snapshot hashing."""
from __future__ import annotations

import pathlib

from real_open_model import artifact_files, sha256_artifact


def test_artifact_hash_is_order_independent_and_covers_all_files(tmp_path: pathlib.Path) -> None:
    (tmp_path / "config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "model-00002-of-00002.safetensors").write_bytes(b"second")
    (tmp_path / "model-00001-of-00002.safetensors").write_bytes(b"first")

    before = sha256_artifact(tmp_path)
    assert [p.name for p in artifact_files(tmp_path)] == [
        "config.json",
        "model-00001-of-00002.safetensors",
        "model-00002-of-00002.safetensors",
    ]

    (tmp_path / "model-00002-of-00002.safetensors").write_bytes(b"SECOND")
    assert sha256_artifact(tmp_path) != before


def test_cache_metadata_is_not_part_of_serving_artifact(tmp_path: pathlib.Path) -> None:
    (tmp_path / "model.safetensors").write_bytes(b"weights")
    cache = tmp_path / ".cache" / "huggingface"
    cache.mkdir(parents=True)
    (cache / "download-metadata.json").write_text("one", encoding="utf-8")

    digest = sha256_artifact(tmp_path)
    (cache / "download-metadata.json").write_text("two", encoding="utf-8")
    assert sha256_artifact(tmp_path) == digest


def test_tamper_simulation_changes_digest_without_writing(tmp_path: pathlib.Path) -> None:
    artifact = tmp_path / "model.safetensors"
    artifact.write_bytes(b"weights")
    original = artifact.read_bytes()

    assert sha256_artifact(artifact, flip_first_byte=True) != sha256_artifact(artifact)
    assert artifact.read_bytes() == original
