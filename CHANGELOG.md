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
