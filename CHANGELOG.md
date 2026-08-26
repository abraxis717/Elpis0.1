## 1.2.9 — Controller lineage authority primitive

- Add an isolated controller-owned process-local lineage authority primitive.
- Precommit rejecting-validator receipts before `P0Controller.run()` returns.
- Reveal each precommitted receipt at most once and consume each bearer capability at most once.
- Reject replay, cross-controller verification, and self-consistent unissued receipts.
- Production validator ingress does not require the receipt yet; C2R6C-B remains open.
- External attestation, cross-process durability, release-binding authority, semantic decomposition, learned re-proposal, competence, and runtime admission remain open.

## 1.2.8 — P0 semantic topology

- Split fixed-position P0 semantics into `grid81.p0-semantic.v1`; generic `grid81.structural.v1` remains the coarse structural/D4 space.
- Bind BasisToken and StructuralOpcode meanings into their respective semantic-space digests.
- Rename the heuristic `decomposition` row to `complexity_flags`; no semantic-decomposition improvement is claimed.
- Replace row-wide task-validator resolution with six predeclared `validation_repair_loci` keyed deterministically by `PythonASTValidator` failure code.
- Keep the global task-derived RELEASE cap at exactly one while allowing all validator repair supports to be active and prebound simultaneously.
- Track the offline Grid81 semantic compiler red-team instrument and run it in qualification/CI.
- External lineage authority, relational task representation, learned re-proposal, held-out competence, and runtime admission remain open.

## 1.2.7 — Round-2 red-team corrections

- Correct the C2R3 mechanism-control claim: the released value is fixture-derived rather than model-derived; the control is not an independent competence test.
- Clarify that C2R5 `lineage_digest` is a deterministic lineage-record digest, not caller-independent provenance attestation.
- Record the open validation-row granularity mismatch: semantic resolution spans nine cells while task-derived RELEASE remains capped at one.
- Run the learned reference-runtime E2E on pull requests as well as branch/main pushes, with a model cache keyed by the pinned raw and converted tensor-state identities; verification remains mandatory on cache hits.
- Reject non-canonical validator-evidence details through typed contract/ingress errors instead of leaking raw JSON serialization exceptions.
- Held-out competence evaluation, external lineage authority, production learned re-proposal, and runtime admission remain separate gates.

## 1.2.6 — P0 artifact/proposal lineage

- Bind controller-produced P0 result contents through projection, structural proposal, decoder plan, artifact, and exact rejecting validator evidence into a deterministic lineage record.
- Require validator ingress records to match the exact artifact, projection, validator identity, and validator evidence payload.
- Keep `cryptographic_external_attestation = false`; the lineage record is an integrity commitment inside the current authority chain, not an independent trust root.
- Production learned re-proposal, generalized semantic feedback, held-out competence, and runtime admission remain false.

## 1.2.5 — Production P0 validator ingress + red-team hardening

- Require exact-state pre-validation release bindings; release owner is no longer copied from live state as its own authorization input.
- Hard-cap one active RELEASE target per feedback traversal; over-cardinality rejects.
- Carry immutable Sudoku givens through feedback and prohibit releasing them; final validation remains bound to original givens.
- Replace the model-derived C2R3 round trip with an independent one-cell hypothesis mechanism control.
- Pin and enforce the converted safetensors tensor-state digest and metadata; `load_model` now verifies before use.
- Keep trace-record digests explicitly non-attesting; held-out model evaluation remains future work.


- Exposed typed production `PythonASTValidator` evidence and exact artifact identity through the R0 adapter without changing its existing transaction-facing ABI.
- Added deterministic pre-validation trace binding from the actual P0 projection through semantic object → topology vertex → P7 capsule/cell support.
- Converted real P0 task-validator failure to coordinate-free `TaskDiagnosticV1` and canonical RELEASE of resolved active support.
- Preserved P0 refinement scope/structural failures as `STRUCTURAL_REJECTION`; they cannot become task residuals.
- Kept task-derived structural mutation RELEASE-only and preserved unrelated clamps.
- Production artifact→structural-proposal lineage, production learned P0 re-proposal, generalized task improvement, and runtime admission remain unproven/false.

## 1.2.4 — Bounded learned feedback traversal

- Added one deterministic C2R3 task-feedback composition step over the already-qualified semantic residual and canonical Projector RELEASE boundaries.
- Re-proposal uses the existing pinned Samsung MLP-T Sudoku runtime; no model-backend abstraction is introduced.
- Learned input is derived only from revised canonical clamp support; task diagnostics, residuals, reverse traces, semantic sidecars, and Projector receipts are not model inputs.
- Task-derived structural mutation remains RELEASE-only; ASSERT/REPLACE remain outside the task-error path.
- Added local and hosted real-checkpoint CPU E2E coverage for RELEASE → revised support → learned re-proposal → validation.
- Preserved surviving clamps and deterministic `run_id + refinement_step_index` traversal identity.
- Bound every task diagnostic `subject_digest` to the exact prior learned proposal digest before residual resolution or structural mutation.
- This remains a mechanism-composition control: generalized task improvement, production validator ingress, production P5/P6/P7 binding, and runtime admission remain unproven/false.

## 1.2.3 — Canonical Projector release adapter

- Promoted the exact qualified R7A RELEASE-planning mechanism through a narrow public adapter.
- Reused canonical DarwinianMatrix `ClampProposal`, `ClampTransaction`, `ClampState`, and transaction application semantics without copying Projector mutation logic.
- Task-derived mutation is RELEASE-only and limited to active support selected by pre-existing reverse trace.
- Current owners are derived from canonical ClampState and stale-state/owner checks remain Projector-owned.
- Added clean-wheel packaging for the minimal canonical Projector surface required by the adapter.
- Preserved the evidence boundary: the release proposal binds to the task diagnostic but does not claim recovery of the clamp's original evidence digest.
- Learned re-proposal remains outside this gate.
- Runtime admission remains false.

## 1.2.2 — Platform-agnostic refinement foundation

- Added a pure-Python platform discovery/build-plan boundary and portable setup entry point.
- Added macOS/Linux/Windows CI for platform/bootstrap and semantic refinement contracts.
- Promoted the qualified R7A task diagnostic, task residual, and semantic/topology reverse-trace contracts.
- Reproduced the exact frozen R7CR3R1 diagnostic, residual, and resolution digests in public tests.
- Kept the pinned Samsung MLP-T TRM as the current learned reference; no model-agnostic runtime claim is made.
- Canonical DarwinianMatrix Projector mutation remains the next promotion gate.
- Runtime admission remains false.

## 1.2.1 — NumPy ABI compatibility hardening

- Constrained NumPy to `>=1.26,<2` because the supported PyTorch 2.2 Intel-macOS wheel is built against the NumPy 1.x ABI.
- Qualified the dependency range through a clean install, strict checkpoint conversion/load, and real learned CPU Sudoku execution.
- Added NumPy to the public third-party dependency inventory.
- Runtime admission remains false.

## 1.2.0 — Public Reference Runtime R1

- Added a runnable, non-authoritative Samsung MLP-T Sudoku reference runtime.
- Pinned architecture, checkpoint revision, and raw checkpoint SHA-256.
- Added strict checkpoint normalization and safetensors conversion.
- Added fail-closed proposal validation: model outputs are never post-hoc repaired and re-attributed to the model.
- Added CPU/CUDA/MPS runtime selection, CLI, tests, clean-clone packaging, health-state reconciliation, and main-branch learned-reference CI.
- Runtime admission remains false; generalized semantic Projector re-projection remains a separate consolidation seam.

# Changelog

## v1.1.1 (2026-08-04)

### Changed
- Grid81 Structural Semantics R1.1 → R1.1.1: Removed candidate-only tests from live test suite
- Added public distribution packaging and CI workflows
- Added portable HACF bridge wrapper source
- Added public verification tooling

### Fixed
- Removed `test_semantics_import_resolves_to_successor_workspace` (candidate-only, post-promotion artifact)
- Removed `test_package_is_loaded_from_successor_workspace` (candidate-only, workspace-dependent)

### Added
- Public README, documentation, license, manifests
- GitHub Actions CI workflow
- Public release verifier
- THIRD_PARTY_NOTICES and license mapping
