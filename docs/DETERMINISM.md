# Determinism Guarantees

## What is deterministic

- D4 group action application on 81-cell grids
- Canonical JSON serialization (key-sorted, no insertion-order dependency)
- Orbit compilation and digest derivation
- Quarantine identity computation
- Structural symbol registry initialization
- HACF exact dense retrieval results
- Retrieval bundle construction and verification
- Runtime R0 transaction execution and replay
- Runtime R1 bounded retrieval with evidence adapter

## What is NOT guaranteed deterministic

- FMS probabilistic memory allocation (approximate)
- Context graph fusion ordering with ties (tie-breaking is implementation-defined)
- Darwinian mutation generation (intentionally stochastic)
- Climate response temperature scaling (environment-dependent)

## Verification methodology

1. Run operation N times in separate processes with `PYTHONHASHSEED` varied
2. Compare SHA-256 digests of all outputs
3. Verify byte-identical canonical serialization
4. Cross-verify orbit digests across consumer implementations

## Requirements

- `PYTHONHASHSEED` may vary; canonical serialization must remain invariant
- No dependency on process ID, timestamp, or memory address
- No external service calls during structural operations
