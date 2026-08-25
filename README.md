# Elpis0.1

Deterministic structural AI core with Grid81 semantics, HACF retrieval, receipt-bound execution, and a runnable learned TRM Sudoku reference runtime.

## Release: v1.2.4 — Bounded Learned Feedback Traversal

The repository contains a clean-clone reference path that downloads and verifies the pinned 5,028,866-parameter Samsung TRM checkpoint, converts the exact checkpoint into `safetensors`, and runs bounded recursive Sudoku inference with a fail-closed given-preservation guard and task validation.

This does **not** mean full Elpis runtime admission. Governance, persistent authority, online serving, and generalized semantic re-projection remain disabled. `runtime_admission` remains `false`.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
elpis model fetch
elpis sudoku solve --file examples/sudoku_one_blank.txt
```

The first `elpis model fetch` downloads the upstream checkpoint, verifies its exact SHA-256 before deserialization, performs a strict model-state ABI normalization, and writes a local `model.safetensors` cache. Model weights are never repository authority.

## Pinned TRM

- Architecture source: `SamsungSAILMontreal/TinyRecursiveModels`
- Architecture commit: `c01103738605ba39d1430519b1ee0c62f4c707f8d`
- Model repository: `Sanjin2024/TinyRecursiveModels-Sudoku-Extreme-mlp`
- Model revision: `256f32fcbe7123e8bf8c449410773a5ad311dbc5`
- Upstream checkpoint: `step_16275`
- Checkpoint SHA-256: `20e9dc7ebf83b9b41a8b3f58f5fd94ee3a7eb0b0d245bdeeb14e2f1488d1daaf`
- Registered parameters: `5,028,866`
- Sequence length: `81`
- Vocabulary: `11`
- Recursive budget: `16`

See `docs/REFERENCE_RUNTIME_PROVENANCE.md` for third-party and checkpoint provenance.

## Reference proposal/validation loop

The public reference runtime keeps the learned model low-authority:

```text
Sudoku givens
  → deterministic token encoding
  → TRM recursive carry update
  → numeric proposal
  → given-preservation structural guard
  → Sudoku validator
  → accept if valid, otherwise continue bounded recursive carry
  → solved or bounded exhaustion
```

The guard **rejects** a proposal that changes a given. It never repairs or rewrites the model output and then attributes the repaired result to the model.

Validation controls only accept/continue inside the learned Sudoku path; they do not select a Grid81 cell/value or inject task semantics into the model. C2R3 now composes one bounded external feedback traversal: a typed task rejection resolves through pre-existing semantic/topology trace, canonical Projector RELEASE reopens implicated active support, and the pinned Samsung TRM re-proposes from the revised support grid.

## Platform portability

The Elpis runtime architecture is platform-neutral. Operating-system,
accelerator, and native-build detection are isolated in
`elpis_reference.platform_setup` and `tools/setup.py`.

The current learned reference remains the pinned Samsung MLP-T TRM. This
release does **not** introduce a model-backend abstraction and does not claim
model agnosticism.

```bash
python tools/setup.py --profile reference --dry-run
python tools/setup.py --profile reference
```

Use `--profile full` to request the native HACF build where it is qualified.
macOS and Linux native paths are supported by the existing CMake boundary;
Windows keeps the portable Python/reference surface while native HACF remains
explicitly unqualified.

## Task-residual refinement foundation

The qualified R7A task diagnostic/residual and semantic/topology reverse-trace
contracts are present in the public package. Their domain-separated digests
reproduce the frozen R7CR3R1 mechanism-control evidence.

C2R2 promotes the qualified R7A RELEASE-planning mechanism as a narrow adapter
to the existing canonical `DarwinianMatrix.projector.constraints` authority.
Resolved support may release a currently active clamp using its current owner;
task failure cannot ASSERT or REPLACE structural claims.

C2R3 adds one bounded, deterministic composition step in
`elpis_reference.feedback_refinement`. A structurally valid prior proposal and
typed task rejection are bound to `run_id + refinement_step_index`, and the
diagnostic `subject_digest` must equal the exact prior proposal digest before
any residual resolution or Projector mutation; reverse trace then resolves
pre-existing support and the canonical Projector applies RELEASE,
and only the revised clamp-derived Sudoku grid is passed to the pinned Samsung
MLP-T reference for re-proposal and validation.

Task diagnostics, task residuals, semantic sidecars, reverse-trace records, and
Projector receipts are not model inputs. The learned model remains
proposal-only and receives no task or structural authority.

This is still a mechanism-composition control. It does not prove generalized
task improvement, production validator ingress, production P5/P6/P7 binding,
arbitrary-task semantic resolution, or runtime admission.

The adapter's proposal evidence digest binds the release request to the task
diagnostic. The current ClampState does not retain the historical evidence
digest that originally created each clamp, so this release makes no stronger
historical-evidence provenance claim.

## Existing qualified structural stack

The canonical structural components remain available under `components/`, including Grid81 semantics, TRMFractalSpine structural contracts, deterministic adjudication, DarwinianMatrix, P0 control, HACF retrieval, and Runtime R0/R1 qualification material.

The legacy qualification commands documented under `docs/BUILD.md` and `docs/TESTING.md` remain applicable to those component paths.

## Explicit exclusions

This release still does **not** activate:

- authoritative SR01 validator admission
- governance or Constitution ratification
- persistent memory writes or AffineL0
- online serving
- SAM integration
- arbitrary-task production semantic re-projection
- persistent cross-reboot logical chronology

## Verification

```bash
pytest -q tests/test_reference_runtime.py
python tools/verify_public_release.py
```

On pushes to `main`, the reference-runtime workflow also fetches the pinned checkpoint, verifies/converts it, and executes the real learned Sudoku reference path on CPU.

## License

Elpis code is MIT unless otherwise noted. The inference-only TRM namespace adaptation is derived from MIT-licensed upstream code; see `docs/REFERENCE_RUNTIME_PROVENANCE.md` and `THIRD_PARTY_NOTICES.md`.

Christ is King
