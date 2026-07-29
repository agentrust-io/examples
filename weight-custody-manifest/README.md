# weight-custody-manifest: Custody for Model Weights

The other examples in this repo govern what an agent may **do**. This one governs the model **weights** themselves: when a builder deploys a model into a customer's own or sovereign infrastructure, how do you prove the weights running in the enclave are exactly the ones the builder shipped, release the decryption key only against a valid hardware attestation, wipe it when custody lapses, and carry the lineage of every derivative?

That is the [Weight Custody Manifest](https://pypi.org/project/weight-custody-manifest/) (WCM): an open protocol and reference SDK. These demos run its real code, roughly one per feature.

For a public open-weight model, base-weight confidentiality is theater (anyone can download the weights), so the same flow does the work that still matters: **integrity and provenance** (is this the model the builder shipped, or a tampered copy), **license as a release condition**, **derivative custody and lineage**, and a **kill switch**.

> **Honest scope.** WCM does not claim silicon-enforced custody against an operator who physically owns the hardware. Cheap published memory-bus attacks (TEE.fail, BadRAM) extract keys from live confidential-computing memory, so against that adversary WCM is accountability-grade (cost, detection, containment, mandatory physical hardening), not cryptographic custody. It is custody-grade against software and remote adversaries. The demos below use a software (mock) attestation provider so they run with no hardware; the hardware-rooted step is validated separately on real SEV-SNP and TDX silicon.

---

## Setup

```bash
git clone https://github.com/agentrust-io/examples.git
cd examples/weight-custody-manifest
pip install -r requirements.txt      # weight-custody-manifest>=0.21.0, Python 3.11+
```

The offline demos need nothing else. `real_open_model.py` needs run-local extras (below).

---

## Start here: the 30-second demo

`refuse_and_wipe.py` is the whole idea in two moments: the weight-decryption key **refuses** to release into an enclave running a tampered serving stack, and **wipe-on-lapse** zeroizes it the moment custody lapses (gone, not suspended).

```bash
python refuse_and_wipe.py
```

The demos below go deeper on the same machinery.

---

## Gate your model load (drop-in)

`load_guard.py` is the smallest useful integration: verify the checkpoint before your loader ever touches it. It checks the manifest's joint signature and that the bytes on disk hash to exactly what the builder bound, then refuses a tampered or swapped fork **before** the load. Drop `guarded_load()` in front of your existing `safetensors` or `transformers` load.

```bash
python load_guard.py                                   # offline: certified loads, tampered refused
python load_guard.py --load --model model.safetensors  # gate + actually load a real file (run-local)
```

---

## The demos

Each script is one runnable feature with mock (software) attestation, so they run anywhere. `refuse_and_wipe.py` above is the 30-second version.

### Closed-weight vs open-weight

The same machinery, two trust settings. **Closed** weights (a frontier model deployed into someone else's infra) need secrecy. **Open** weights (Llama, Mistral, SmolLM) are already public, so the flow instead does integrity, license, and derivative custody.

- **`closed_model_e2e.py`** -- the closed/frontier flow where secrecy is the job (`base_confidentiality: confidential`): sign, attestation-gated release of the real decryption key, wipe-on-lapse custody, and the honest hostile-owner caveat.
- **`open_model_e2e.py`** -- the full six-step flow on an open model, honest about which steps are real work versus theater for a public base (the base's secrecy is theater; integrity, license, derivative custody, and the kill switch are the point).

### The four layers, feature by feature

- **`multi_stage_byom.py`** -- Layer 4 at depth (SPEC 3.8): a base to derivative to derivative chain, monotone rights (a derivative narrows but never widens), release gated on every upstream being logged, and a revocation cascading down the chain.
- **`revocation_kill_switch.py`** -- the kill switch: a serving session, a revocation, and the enclave stopping at the next cadence lapse (the key is zeroized, not suspended).
- **`channel_binding.py`** -- Layer 2 relay defense (CVE-2026-33697): the released key is sealed to the enclave's attested transport key, so a relayed attestation gets only ciphertext it cannot open.
- **`sovereign_self_custody.py`** -- 2-of-3 threshold release (SPEC 3.5): no single party, and no single forged quote, can assemble the key.

### Transparency, post-quantum, provenance

- **`transparency_log.py`** -- the append-only Merkle log (SPEC 3.7 / RFC 9162): inclusion and consistency proofs, and a monitor detecting a suppressed revocation.
- **`post_quantum.py`** -- sign and verify a manifest with ML-DSA-65 and with the Ed25519+ML-DSA-65 hybrid profile.
- **`provenance_model_signing.py`** -- interop with OpenSSF model-signing: a WCM manifest references a model-signing signature as its provenance, and `verify_provenance` cryptographically verifies it. Needs the extra: `pip install "weight-custody-manifest[model-signing]"`.

### Verifying real attestations

- **`snp_replay.py`** -- replay a recorded AMD SEV-SNP quote offline: parse the report, verify the VCEK to ASK to ARK chain to a trusted AMD root, the report signature, and the nonce binding. A synthetic bundle is committed in `fixtures/`; pass a captured bundle to replay genuine silicon.
- **`quote_verification.py`** -- the verifier machinery against a synthetic PKI: cert chain, report signature, and nonce binding, passing and failing (untrusted root, tampered report, nonce mismatch). This is the same machinery the SEV-SNP, TDX, and NVIDIA GPU verifiers plug into.

### Over real weights (run-local)

- **`real_open_model.py`** -- the flow over a real open model's actual bytes: it downloads SmolLM2-135M (~270MB), hashes its real safetensors into the manifest, includes a tamper demo (a one-byte-flipped fork no longer matches), and with `--infer` loads the model and generates. Network and heavy, so it is run-local and excluded from CI.

```bash
python closed_model_e2e.py                             # any of the offline examples
pip install "weight-custody-manifest[model-signing]"   # for provenance_model_signing.py
pip install -r requirements-infer.txt                  # for real_open_model.py
python real_open_model.py
```

---

## What runs in CI

Every offline example runs in CI against the published PyPI package and must exit 0: `refuse_and_wipe`, the closed/open e2e pair, `multi_stage_byom`, `revocation_kill_switch`, `channel_binding`, `sovereign_self_custody`, `transparency_log`, `post_quantum`, `quote_verification`, `load_guard`, `snp_replay`, and `provenance_model_signing` (with the `[model-signing]` extra). Only `real_open_model.py` is excluded (it downloads a model).

## Reference

- Package: [weight-custody-manifest on PyPI](https://pypi.org/project/weight-custody-manifest/)
- `manifest.example.json` in this folder is a sample signed manifest for reference.

## License

Apache 2.0. See [LICENSE](../LICENSE) in the repo root.
