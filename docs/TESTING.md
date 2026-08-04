# Testing Strategy

## Test categories

### Direct tests
Unit tests exercising each component's public API surface. Covers contract invariants, negative cases, input non-mutation, and structural properties.

### Consumer compatibility tests
Verify that downstream consumers can import alongside the primary semantics package, with consistent D4 action definitions and canonical serialization.

### Determinism tests
Cross-process verification: run operations in separate Python processes and compare SHA-256 digests of outputs.

### Negative case tests
Exhaustive coverage of rejection paths: invalid opcodes, out-of-bound indices, malformed payloads, unknown action kinds.

### Fresh-process determinism
Five independent process invocations producing identical outputs for identical inputs.

## Test counts

| Suite | Direct | Negative | Determinism | Consumer |
|-------|--------|----------|-------------|----------|
| Grid81 R1.1.1 | 122/122 | 37 | 9 | 5 |
| Runtime R0 | 26/26 | 13 | 5 | — |
| Runtime R1 | 24/24 | 12 | 5 | — |
