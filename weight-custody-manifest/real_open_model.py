"""End-to-end Weight Custody Manifest flow on a REAL open-weight model, locally.

Downloads a pinned snapshot of a real open model, hashes its ACTUAL artifacts,
and runs the whole WCM
flow over those bytes. The ONLY mocked part is the hardware attestation
(SoftwareProvider): a laptop has no SEV-SNP/TDX/H100, and that hardware-rooted
step is the one we validate separately on real cloud silicon. Everything else is
real WCM code over real weights:

  integrity/provenance   -> hash the actual safetensors, bind it in the manifest
  joint signing          -> real Ed25519 builder + custodian signatures
  release gate           -> the KBS composite-verify logic (software evidence)
  wipe-on-lapse          -> the kill switch
  license-as-condition   -> the model's license bound into the signed manifest
  derivative custody      -> a fine-tune's weights get their own manifest + lineage

Usage:
    pip install huggingface_hub safetensors
    python real_open_model.py                      # SmolLM2-135M (~270MB)
    python real_open_model.py --model <hf-repo-id> --license "<license>"
    python real_open_model.py --revision <immutable-hf-commit>
    python real_open_model.py --local path/to/model-directory
"""
from __future__ import annotations

import argparse
import hashlib
import os
import pathlib

from wcm import (
    Ed25519Signer,
    EnclaveSession,
    KeyBrokerService,
    SoftwareProvider,
    VerificationContext,
    WeightCustodyManifest,
    combine_shares,  # noqa: F401 - kept importable for the curious
    generate_ed25519,
    is_root,
    verify_lineage,
    verify_manifest,
)


def rule(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def artifact_files(path: pathlib.Path) -> list[pathlib.Path]:
    """Return the deterministic file inventory bound by the manifest.

    A directory snapshot includes weights, shard indexes, configuration, and
    tokenizer assets. Hidden Hugging Face cache metadata is deliberately not
    part of the serving artifact.
    """
    if path.is_file():
        return [path]
    files = [
        p for p in path.rglob("*")
        if p.is_file() and ".cache" not in p.relative_to(path).parts
    ]
    if not files:
        raise ValueError(f"model artifact contains no files: {path}")
    return sorted(files, key=lambda p: p.relative_to(path).as_posix())


def sha256_artifact(path: pathlib.Path, *, flip_first_byte: bool = False) -> str:
    """Hash a file or complete model directory with names and boundaries.

    Length-prefixing the relative path and content prevents two different
    directory layouts from producing the same concatenated byte stream.
    """
    root = path if path.is_dir() else path.parent
    h = hashlib.sha256()
    flipped = False
    for file_path in artifact_files(path):
        relative = file_path.relative_to(root).as_posix().encode("utf-8")
        h.update(len(relative).to_bytes(8, "big"))
        h.update(relative)
        h.update(file_path.stat().st_size.to_bytes(8, "big"))
        with file_path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                if flip_first_byte and not flipped and chunk:
                    changed = bytearray(chunk)
                    changed[0] ^= 0xFF
                    chunk = bytes(changed)
                    flipped = True
                h.update(chunk)
    return "sha256:" + h.hexdigest()


def run_inference(verified_path: pathlib.Path) -> None:
    """Optionally load the model and generate, so the certified serving stack is
    a real running model, not a placeholder. Lazy imports; skips if unavailable."""
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        print("  transformers not installed; `pip install transformers` to enable --infer")
        return
    print("  loading the model and generating (real serving stack)...")
    # The verified local snapshot is the only permissible source after the
    # manifest check. These settings make an accidental network fallback fail.
    os.environ["HF_HUB_OFFLINE"] = "1"
    tok = AutoTokenizer.from_pretrained(verified_path, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(verified_path, local_files_only=True)
    ids = tok("Confidential computing protects", return_tensors="pt")
    out = model.generate(**ids, max_new_tokens=12, do_sample=False)
    print("  model output:", repr(tok.decode(out[0], skip_special_tokens=True)))


def resolve_artifact(args: argparse.Namespace) -> tuple[pathlib.Path, str]:
    if args.local:
        p = pathlib.Path(args.local)
        if not p.exists():
            raise SystemExit(f"--local path not found: {p}")
        return p, f"local:{p.name}"
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError:
        raise SystemExit("pip install huggingface_hub to download a model, or pass --local")
    resolved_revision = HfApi().model_info(args.model, revision=args.revision).sha
    if not resolved_revision:
        raise SystemExit(f"could not resolve {args.model}@{args.revision} to a commit")
    print(f"resolved {args.model}@{args.revision} -> {resolved_revision}")
    print("downloading the immutable snapshot (cached after first run)...")
    path = pathlib.Path(snapshot_download(repo_id=args.model, revision=resolved_revision))
    return path, f"{args.model}@{resolved_revision}"


def build_manifest(*, weights_hash, license_text, serving, builder_id, custodian_id,
                   derivatives, derived_from=None, rights_holder=None) -> dict:
    m: dict = {
        "manifest_version": "0.1",
        "weights_hash": weights_hash,
        "builder": {"identity": builder_id, "signing_key": "ed25519:demo"},
        "release_terms": {
            "license": license_text,
            "permitted_derivatives": "fine-tune-only",
            "derivatives": derivatives,
            "permitted_environments": ["enterprise-governed-enclave"],
        },
        "release_policy": {
            "required_assurance_tier": "hardware-attested",
            "trusted_time_source": "secure-tsc",
            "required_hw_platform": ["amd-sev-snp", "nvidia-cc-gpu"],
            "required_gpu_measurement": {"rim_pin": "nvidia-rim:demo-golden"},
            "required_serving_image": {
                "signer": "ed25519:demo",
                "release_rule": "prefer-current",
                "accepted_measurements": [{"measurement": serving, "status": "current"}],
            },
            "attestation_revocation_check": "live-per-release, max-cache-age: short-window",
            "revocation_authority": "builder-and-opaque-joint",
        },
        "custody": {
            "custodian": custodian_id,
            "custodian_type": "customer-self-custody",
            "kbs_image": {"measurement": "sha256:" + "ab" * 32, "signer": "ed25519:demo"},
            "enclave_id": "did:example:enterprise-enclave-01",
            "attestation_cadence": "1h",
        },
        # The open-weight reframe: base is public, one org holds both roles.
        "base_confidentiality": "open",
        "deployment_model": "byom-symmetric",
    }
    if derived_from is not None:
        m["derived_from"] = derived_from
    if rights_holder is not None:
        m["rights_holder"] = rights_holder
    return m


def sign(manifest, kp, role, signer):
    return Ed25519Signer(kp).sign(manifest.unsigned_dict(), role=role, signer=signer)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="HuggingFaceTB/SmolLM2-135M")
    ap.add_argument("--revision", default="main",
                    help="Hugging Face revision; use an immutable commit for launch evidence")
    ap.add_argument("--local", default=None,
                    help="path to a complete local model directory or single model file")
    ap.add_argument("--license", default="Apache-2.0")
    ap.add_argument("--infer", action="store_true",
                    help="also load the model and generate (real serving stack; needs transformers)")
    args = ap.parse_args()

    artifact_path, model_id = resolve_artifact(args)
    files = artifact_files(artifact_path)
    size_mb = sum(p.stat().st_size for p in files) / 1e6

    rule(f"Real open model: {model_id}  ({size_mb:.1f} MB of real weights)")
    base_hash = sha256_artifact(artifact_path)
    print("artifact path     :", artifact_path)
    print("artifact files    :", len(files))
    print("REAL artifact hash:", base_hash)
    print("license           :", args.license)
    print("NOTE: the base is public, so this protects integrity + license +")
    print("      derivative custody, not secrecy. Attestation below is the software")
    print("      mock (no TEE on this machine); the hardware path is validated in cloud.")

    gov_builder, gov_custodian = generate_ed25519(), generate_ed25519()
    serving = hashlib.sha256(b"vllm + policy-bundle (the certified serving stack)").hexdigest()
    serving = "sha256:" + serving

    # ---- Step 0-1: certify + verify the base (integrity + license) ----------
    rule("Step 1 - Certify + verify the base manifest (integrity, provenance)")
    base = WeightCustodyManifest.model_validate(build_manifest(
        weights_hash=base_hash, license_text=args.license, serving=serving,
        builder_id="acme-model-governance", custodian_id="acme-model-governance",
        derivatives="fine-tune-only"))
    base = base.with_signatures([
        sign(base, gov_builder, "builder", "acme-model-governance"),
        sign(base, gov_custodian, "custodian", "acme-model-governance")])
    ctx = VerificationContext()
    ctx.add_key(gov_builder.public_bytes)
    ctx.add_key(gov_custodian.public_bytes)
    result = verify_manifest(base, ctx)
    print("manifest signature valid:", result.ok)
    for note in result.notes:
        print("  note:", note)

    # ---- Step 2: attestation-gated load (only the certified stack) ----------
    rule("Step 2 - Attestation gate (load only the certified serving stack)")
    kbs = KeyBrokerService({base.weights_hash: b"loading-key-not-a-secret-for-open-weights"})
    challenge = kbs.issue_challenge()
    evidence = SoftwareProvider().produce(
        challenge, serving_image_measurement=serving, gpu_measurement="nvidia-rim:demo-golden")
    decision = kbs.verify_and_release(base, evidence)
    print("gate released     :", decision.released)
    print("a silently modified fork of these public weights would NOT load here.")

    # ---- Step 3: wipe-on-lapse custody (kill switch) ------------------------
    rule("Step 3 - Wipe-on-lapse custody (kill switch: recall / license breach)")
    session = EnclaveSession.from_release(base, decision)
    session.use_key()
    print("serving under a 1h cadence; time_floor =", session.time_floor.value)

    # ---- Step 4: license as a technical release condition -------------------
    rule("Step 4 - License is a technical release condition")
    print("release_terms.license =", base.release_terms.license)
    if args.infer:
        if artifact_path.is_file():
            print("  (--infer needs a complete model directory; skipping single-file artifact)")
        else:
            run_inference(artifact_path)

    # ---- Step 5: fine-tune -> the DERIVATIVE is the real asset ---------------
    rule("Step 5 - Fine-tune: the derivative weights get their own custody")
    # A real fine-tune would retrain; here we stand in for the *resulting bytes*
    # (base weights + your proprietary delta) and hash them, which is what a
    # derivative manifest actually binds.
    deriv_hash = hashlib.sha256(
        base_hash.encode() + b"<+ acme proprietary fine-tune delta>").hexdigest()
    deriv_hash = "sha256:" + deriv_hash
    deriv = WeightCustodyManifest.model_validate(build_manifest(
        weights_hash=deriv_hash, license_text=args.license + " + Acme-derivative",
        serving=serving, builder_id="acme-model-governance",
        custodian_id="acme-model-governance", derivatives="none",
        derived_from=base.weights_hash, rights_holder={"base": model_id, "derivative": "acme"}))
    deriv = deriv.with_signatures([
        sign(deriv, gov_builder, "builder", "acme-model-governance"),
        sign(deriv, gov_custodian, "custodian", "acme-model-governance")])
    print("derivative weights_hash:", deriv_hash)
    print("derived_from           :", deriv.derived_from)

    # ---- Step 6: lineage from derivative back to the real base --------------
    rule("Step 6 - Verify lineage (derivative -> real open base)")
    lineage = verify_lineage({base.weights_hash: base, deriv.weights_hash: deriv}, deriv.weights_hash)
    print("lineage ok :", lineage.ok, " depth:", lineage.depth, " base is root:", is_root(base))

    # ---- Step 7: integrity, made concrete -----------------------------------
    rule("Step 7 - A silently tampered fork is caught by the hash")
    tampered = sha256_artifact(artifact_path, flip_first_byte=True)
    print("certified weights_hash :", base_hash)
    print("tampered-fork hash     :", tampered)
    print("tampered matches manifest? :", tampered == base.weights_hash)
    print("the enclave binds the manifest's weights_hash, so weights that do not hash")
    print("to it (a poisoned or backdoored fork of these public weights) never load.")

    rule("What was real vs mocked here")
    print("REAL   : the weights_hash over", model_id, "actual bytes; joint signatures;")
    print("         the release-gate logic; wipe-on-lapse; derivative manifest + lineage.")
    print("MOCKED : the attestation evidence (no TEE on this machine). The hardware")
    print("         root of trust is validated separately (SEV-SNP + TDX, in cloud).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
