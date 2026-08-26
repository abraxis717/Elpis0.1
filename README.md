# Elpis0.1

Deterministic structural AI core with Grid81 semantics, HACF retrieval, receipt-bound execution, and a runnable learned TRM Sudoku reference runtime.

## Release: v1.2.12 — Relational semantic request contract

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

### C2R4 production P0 validator ingress

C2R4 closes the first production feedback-boundary gap. The R0 AST adapter now
exposes the actual typed `PythonASTValidator` evidence together with the exact
artifact digest while preserving the existing transaction-facing validator ABI.

The public refinement seam freezes a semantic/topology/P7 reverse trace from
the real P0 projection before validation. A failed task validator binds to the
artifact digest and the projection's semantic `validation` object; it does not
select a Grid81 cell or value. Reverse trace then resolves that pre-existing
semantic support and the canonical DarwinianMatrix Projector may RELEASE only
currently active support.

P0 refinement scope/structural rejection remains `STRUCTURAL_REJECTION` and is
still barred from task-residual conversion.

C2R4 does not claim production learned re-proposal. The production Python
artifact currently lacks a qualified identity lineage back to a production
learned structural proposal, so reconnecting a production proposer remains the
next gate. Runtime admission remains false.

### C2R4 red-team hardening

The C2R4 candidate also hardens defects found by adversarial review before publication. RELEASE planning no longer copies the live owner out of `ClampState` as its own authorization input: it requires a state-bound, pre-validation release binding record whose owner and semantic locus must match the resolved active support. One traversal is hard-capped at one RELEASE target and rejects over-cardinality rather than truncating. The binding digest is a deterministic commitment, not a signature or independent attestation.

For the Sudoku reference traversal, original puzzle givens are immutable hard support. They must be present in the pre-release clamp state, may not be RELEASE targets, and remain the validator input for the final learned proposal. RELEASE is therefore described as bounded search-space widening of a retractable hypothesis, not as intrinsically fail-closed.

The C2R3 learned E2E no longer installs model-produced output as the support it later releases. Its retractable one-cell value is derived from the deterministic solved-board fixture used by the mechanism control, not from the learned model. The release/revised-input assertions therefore verify feedback plumbing only; they are intentionally not evidence of model competence or independent problem-solving.

The converted safetensors tensor state is now pinned by a canonical tensor-state SHA-256 derived from the raw checkpoint after its existing raw SHA verification. `verify_model` and `load_model` reject tensor or metadata tampering.

Generic reverse-trace records remain deterministic records rather than signed attestations; repository text must not treat `trace_proof_digests` as cryptographic proof. A held-out competence evaluation remains a separate gate.


### C2R5 artifact/proposal lineage boundary

C2R5 adds deterministic integrity checks across the P0 result, projection, structural proposal,
decoder control plan, artifact, and selected validator evidence. The resulting `lineage_digest`
is a **lineage record digest**: it detects mutation/substitution inside a supplied record, but it is
not a signature, controller-issued capability, temporal precommitment, or independent provenance
attestation. The current validator ingress externally rechecks the artifact, projection, and exact
validator evidence against that record; the proposal/plan/result identities inside the record are
not yet anchored to a caller-independent controller registry.

v1.2.7 left the production validator diagnostic at row granularity: one semantic
`validation` object reverse-resolved to nine cells while task-derived RELEASE remained capped at
one. C2R6B replaces that row-wide task locus with fixed pre-validation cell-role semantics.

### C2R6B P0 semantic topology

P0 now declares a distinct fixed-position semantic space, `grid81.p0-semantic.v1`, rather than
sharing the generic `grid81.structural.v1` identity used by the coarse structural/D4 substrate.
The P0 schema digest commits the BasisToken id-to-name mapping, every semantic row and column role,
the coarse structural bridge, the validator-failure repair-role map, and the fact that the only
admitted P0 semantic D4 element is `IDENTITY`. The generic structural-space digest separately
commits its `StructuralOpcode` mapping.

The former `decomposition` row is renamed `complexity_flags`: its behavior is unchanged and is not
claimed as genuine task decomposition. The former `validation` row becomes
`validation_repair_loci`. Each supported `PythonASTValidator` rejection code deterministically
selects one predeclared semantic repair role. Reverse trace therefore resolves a task-validator
failure to exactly one pre-validation cell even when every validator repair support is active.
The global task-derived RELEASE cap remains exactly one; unrelated validator repair loci and
unrelated structural support remain clamped.

C2R6B closes the granularity deadlock and semantic-space aliasing at the canonical P0 run
boundary.

### C2R6C-A controller-associated lineage issuance registry

The first C2R6C-A candidate passed its registry mechanics but failed adversarial ownership review:
the issuer was publicly constructible, `P0Controller` accepted a caller-supplied authority, and a
public verifier selector made an unsafe future ingress topology too easy to construct.

v1.2.10 closes those supported-surface defects. Supported `P0Controller` construction creates one
internal issuance/consumption registry and accepts no authority injection. The old public standalone
issuer and public verifier selector are removed. Rejecting-validator receipts are still precommitted
before `run()` returns; one-shot membership, replay rejection, distinct-authority-instance rejection,
and rejection of self-consistent but unissued receipts remain. Concurrent reveal/consume transitions
are serialized and fail with typed authority errors, and the receipt digest uses the repository NUL
domain-separator convention.

The strongest current phrase is **controller-associated in-memory issuance registry**. Python
reflection can still reach implementation-private state, so hostile same-process isolation is not
claimed. Strong-reference tombstones also retain rejecting `P0Result` graphs for the controller
lifetime and remain an explicit prototype lifecycle limitation.

C2R6C-B now binds production P0 validator ingress once to an exact `P0Controller` during trusted
composition. Per-request ingress accepts no controller, verifier, authority root, or consumption
callback: it accepts only the controller-produced authorization plus evidence/trace inputs. Passed
or unsupported evidence and lineage mismatches fail before capability consumption; after those
checks pass, the bound controller consumes registry membership exactly once and the diagnostic
details digest binds the authority instance, capability, receipt, and consumption digests.

This closes the caller-supplied-lineage N2 defect at the production P0 validator ingress API under
the declared process-local composition trust model. It does **not** establish hostile same-process
isolation, cross-process durability, external cryptographic attestation, independent temporal
ReleaseBinding issuance, relational/ECS decomposition, semantic reconstruction quality, learned
re-proposal, competence, feedback efficacy, or runtime admission. Strong-reference authority
tombstones remain an explicit lifecycle limitation.

### C2R7-A relational semantic request contract

P0 now has a canonical typed semantic request graph independent of Grid81. The graph preserves
explicit entity identity/type, operation identity and ordered arguments, constraints with negation,
directed relations, directed operation dependencies, integer quantities beyond the old four-parameter
cell limit, and explicit output identities. Declaration order is canonicalized while argument and
edge direction remain semantic. Referential integrity, globally unique node identities, digest
integrity, and acyclic operation dependencies fail closed.

This is a **representation contract**, not a natural-language semantic compiler. The existing
`DeterministicPythonProjector` remains the same word-set/complexity heuristic for legacy
`RequestContext` values. If a `P0SemanticRequestV1` is present, that projector now rejects instead of
silently dropping the graph. C2R7-B must explicitly bind the semantic graph identity to the
structural-control path; it must not imply that the arbitrary graph has been losslessly stuffed into
81 cells.

Natural-language extraction, paraphrase normalization, semantic reconstruction quality,
semantic-graph/Grid81 sidecar binding, relational ECS dynamics, learned semantic compilation,
held-out competence, and runtime admission remain unproven.

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
