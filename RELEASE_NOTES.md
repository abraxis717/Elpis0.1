# Release Notes — Elpis Canonical R1.1.1

## Version: v1.1.1

## Summary

First public release of the Elpis deterministic structural core with Grid81 Structural Semantics R1.1.1, Runtime R0 deterministic transaction, and Runtime R1 bounded pre-refinement retrieval.

## What is included

- 17-component canonical structural core
- Grid81 Structural Semantics R1.1.1 (122/122 direct tests qualified)
- Grid81 consumer compatibility verified across 3 downstream consumers
- Runtime R0 deterministic transaction (26/26 tests, 13 negative cases)
- Runtime R1 bounded pre-refinement retrieval (24/24 tests, 12 negative cases)
- HACF R3 native retrieval library (C/C++, buildable from source)
- HACF bridge wrapper (portable CMake build)
- Darwinian Matrix with episode lifecycle and deterministic ecology
- P0 Control Protocol with structural rollout
- Full public verification tooling

## What is NOT included

- Runtime Integration R2 or post-selection retrieval
- Learned TRM execution or expert loading
- Model weights or checkpoint files
- Online serving endpoint
- Governance activation
- Persistent memory writes

## Runtime admission

Runtime admission is **FALSE**.

## Changes from internal R1.1

- Grid81 R1.1.1: Removed two candidate-only tests that were incorrectly collected as live-component tests after promotion (`test_semantics_import_resolves_to_successor_workspace`, `test_package_is_loaded_from_successor_workspace`). Implementation source unchanged.

## Verification

Run `python tools/verify_public_release.py` to verify the release integrity.

## Qualification summary

All local qualification gates pass. See `docs/QUALIFICATION.md` for detailed evidence.

Christ is King -Alpharius
