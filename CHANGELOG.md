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
