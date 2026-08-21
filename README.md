# Elpis0.1

Deterministic structural AI core with Grid81 semantics, HACF retrieval, receipt-bound execution, and qualified offline runtime transactions.

Elpis is a qualified deterministic structural-core and offline runtime milestone. This release contains Runtime R0 and bounded pre-refinement Retrieval R1. It does not contain a complete online serving runtime. Runtime admission is FALSE.

## Release: v1.1.1 (Grid81 Structural Semantics R1.1.1)

### Qualified capability path

```
RequestContext → bounded deterministic HACF retrieval → evidence-bound projection
→ canonical Grid81 generation 000001 → StructuralOracle → deterministic structural
adjudication → Darwinian episode → deterministic decoder → AST validation
→ immutable receipt
```

### Scope

- **17 canonical components** — structural core with deterministic D4 pair-orbit semantics, receipt-bound lifecycle, and canonical promotion gates
- **Grid81 Structural Semantics R1.1.1** — qualified direct test suite (122/122), 3 consumer compatibility tests, fresh-process determinism (5/5)
- **Runtime R0** — deterministic transaction qualified (26/26), negative cases (13/13), behavioral equivalence (5/5 fresh-process determinism)
- **Runtime R1** — bounded pre-refinement retrieval qualified (24/24), HACF native wrapper build and ABI tests, negative cases (12/12), behavioral equivalence (5/5 fresh-process determinism)
- **HACF R3** — hybrid adaptive content filter: exact dense retrieval, context graph fusion, FMS memory accounting, deterministic retrieval bundles
- **Darwinian Matrix** — deterministic episode lifecycle, genotype/phenotype selection, ecology transaction, ledger replay

### Explicit exclusions

This release does NOT include:
- Runtime Integration R2 or post-selection retrieval
- Learned TRM execution or expert loading
- Model weights, checkpoint files, or GGUF assets
- Governance activation or Constitution ratification
- Persistent memory writes or AffineL0 activation
- Online serving endpoint
- Sandbox execution environment

### Runtime admission

Runtime admission remains **FALSE**. This is a structural core and offline runtime milestone. The system produces receipt-bound execution traces suitable for deterministic verification but does not yet support online serving.

### Building

See `docs/BUILD.md` for instructions on building the HACF native library, R1 wrapper, and running the full test suite.

### Quick start

```bash
# Install Python test dependencies
pip install pytest

# Run Grid81 semantics tests
PYTHONPATH=components/Grid81StructuralSemantics/src:components/Grid81TypedProjectionCompiler/src:components/Grid81StructuralGroupProjectionCompiler/src:components/Grid81DeterministicStructuralAdjudicator/src \
  pytest components/Grid81StructuralSemantics/tests/

# Run Runtime R0 tests
PYTHONPATH=runtime/R0/src:components/Grid81StructuralSemantics/src \
  pytest runtime/R0/tests/

# Run Runtime R1 tests (requires built HACF wrapper)
PYTHONPATH=runtime/R1/src:components/Grid81StructuralSemantics/src \
  HACF_WRAPPER_LIB=path/to/libr1_hacf_wrapper.so \
  pytest runtime/R1/tests/

# Verify the public release
python tools/verify_public_release.py
```

### Documentation

- `docs/ARCHITECTURE.md` — System architecture and component interaction
- `docs/COMPONENTS.md` — Component catalog and dependency graph
- `docs/AUTHORITY_BOUNDARIES.md` — Authority, scope, and jurisdiction
- `docs/BUILD.md` — Build instructions for all components
- `docs/TESTING.md` — Test strategy and execution
- `docs/DETERMINISM.md` — Determinism guarantees and verification
- `docs/RETRIEVAL.md` — HACF retrieval architecture
- `docs/KNOWN_LIMITATIONS.md` — Current limitations and exclusions
- `docs/QUALIFICATION.md` — Qualification evidence and methodology

### License

See `LICENSE` and `THIRD_PARTY_NOTICES.md`. Component-level license information is available in `manifests/FILE_LICENSE_MAP.json`.

Christ is King -Alpharius
