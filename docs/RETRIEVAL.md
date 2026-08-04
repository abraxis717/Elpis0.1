# Retrieval Architecture

## HACF R3

Hybrid Adaptive Content Filter providing deterministic retrieval capabilities:

### Exact dense vector retrieval
- CPU-based exact nearest neighbor search
- Vector sharding with manifest tracking
- Deterministic embedding provider interface

### Context graph fusion
- Graph-based context expansion over retrieval results
- FMS memory accounting for bounded allocation
- Retrieval bundle construction with integrity verification

### R1 wrapper
- Python FFI bridge to HACF C library
- Budget enforcement with fail-closed overflow
- Evidence adapter with canonical identity binding
- Query derivation with deterministic materialization

## Retrieval flow

```
RequestContext
  → Query derivation (deterministic)
  → HACF exact retrieval (bounded K)
  → Context graph expansion (bounded depth)
  → Retrieval bundle assembly
  → Bundle integrity verification
  → Evidence adapter binding
  → Runtime R1 transaction
```

## Budget constraints

- Maximum retrieval K configurable per query
- Context graph expansion depth bounded
- Memory allocation tracked via FMS
- Fail-closed on budget exhaustion
