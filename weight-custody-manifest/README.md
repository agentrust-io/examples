# weight-custody-manifest: Custody for Model Weights

The other examples in this repo govern what an agent may **do**. This one governs the model **weights** themselves: when a builder deploys a model into a customer's own or sovereign infrastructure, how do you prove the weights running in the enclave are exactly the ones the builder shipped, release the decryption key only against a valid hardware attestation, wipe it when custody lapses, and carry the lineage of every derivative?

That is the [Weight Custody Manifest](https://pypi.org/project/weight-custody-manifest/) (WCM): an open protocol and reference SDK. These four demos run its real code.

For a public open-weight model, base-weight confidentiality is theater (anyone can download the weights), so the same flow does the work that still matters: **integrity and provenance** (is this the model the builder shipped, or a tampered copy), **license as a release condition**, **derivative custody and lineage**, and a **kill switch**.

> **Honest scope.** WCM does not claim silicon-enforced custody against an operator who physically owns the hardware. Cheap published memory-bus attacks (TEE.fail, BadRAM) extract keys from live confidential-computing memory, so against that adversary WCM is accountability-grade (cost, detection, containment, mandatory physical hardening), not cryptographic custody. It is custody-grade against software and remote adversaries. The demos below use a software (mock) attestation provider so they run with no hardware; the hardware-rooted step is validated separately on real SEV-SNP and TDX silicon.

---

## Setup

```bash
git clone https://github.com/agentrust-io/examples.git
cd examples/weight-custody-manifest
pip install -r requirements.txt      # weight-custody-manifest>=0.19.0, Python 3.11+
```

The three offline demos need nothing else. `real_open_model.py` needs run-local extras (below).

---

## The demos

### 1. `open_model_e2e.py` -- the whole flow, end to end

The full six-step Weight Custody Manifest flow on an open-weight model with a mock attestation provider: sign the joint manifest (builder + custodian), run the attestation-gated key release, hold the key under a wipe-on-lapse custody lease, enforce the license as a release condition, then fine-tune into a derivative and verify its lineage back to the base. Narrated, and honest about which steps are real work versus theater for a public model. Runs anywhere.

```bash
python open_model_e2e.py
```

### 2. `sovereign_self_custody.py` -- threshold release, no single point of trust

Sovereign self-custody with a 2-of-3 threshold split-key (SPEC 3.5): the release key is split with Shamir secret sharing so no single party can release the weights alone. Real WCM code, software attestation, runs anywhere.

```bash
python sovereign_self_custody.py
```

### 3. `snp_replay.py` -- replay a real attestation, offline

The CPU half of Layer 2's composite verification (SPEC 3.2), run offline against a recorded AMD SEV-SNP quote. It exercises exactly what a key broker runs before releasing a key: parse the SNP report, verify the VCEK to ASK to ARK certificate chain to a trusted AMD root, verify the report's own signature, and confirm REPORT_DATA binds the challenge nonce (anti-replay). A synthetic bundle is committed in `fixtures/` so it runs anywhere; pass a captured bundle to replay genuine silicon.

```bash
python snp_replay.py                         # committed synthetic bundle
python snp_replay.py path/to/snp_quote.json  # a bundle captured on a real Azure SEV-SNP CVM
```

### 4. `real_open_model.py` -- run-local, over real weights

The same flow over a **real** open model's actual bytes: it downloads an open model (SmolLM2-135M by default, ~270MB), hashes its real safetensors into the manifest, includes a tamper demo (a one-byte-flipped fork no longer matches the manifest), and with `--infer` loads the model and generates so the certified serving stack is a real running model. Network and heavy, so it is run-local and excluded from CI.

```bash
pip install -r requirements-infer.txt
python real_open_model.py                    # download, hash, full flow, tamper demo
python real_open_model.py --infer            # also load the model and generate
python real_open_model.py --local path/to/model.safetensors   # skip the download
```

---

## What runs in CI

The three offline demos (`open_model_e2e.py`, `sovereign_self_custody.py`, `snp_replay.py`) run in CI against the published PyPI package and must exit 0. `real_open_model.py` is not in CI (it downloads a model).

## Reference

- Package: [weight-custody-manifest on PyPI](https://pypi.org/project/weight-custody-manifest/)
- `manifest.example.json` in this folder is a sample signed manifest for reference.

## License

Apache 2.0. See [LICENSE](../LICENSE) in the repo root.
