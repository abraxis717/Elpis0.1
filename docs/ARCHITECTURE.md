# Architecture

Elpis is a deterministic structural-core system organized around receipt-bound transactions, canonical promotion gates, and D4 group-theoretic structural semantics over 81-cell grids.

## Layer overview

### Native retrieval layer (HACF R3)
- Exact dense vector retrieval with FMS memory accounting
- Context graph fusion for hybrid retrieval
- Deterministic retrieval bundles with replay verification
- C/C++ implementation, portable CMake build

### Semantic structural spine (V1)
- Bounded semantic view selection with context deficit tracking
- Evidence admission policy and typed evidence views
- Hypergraph topology with constraint propagation
- TRM adapter interface for refinement integration

### Grid81 structural semantics (R1.1.1)
- D4 group action on 81-cell grids with orbit compilation
- Canonical serialization via deterministic JSON + SHA-256
- Quarantine identity derivation
- Structural symbol registry with passive projection contracts
- Three downstream consumers: typed projection, group projection, adjudication

### Canonical substrate (Grid81 generation 000001)
- Immutable canonical grid state with authority audit
- Transaction manifest with capability lifecycle tracking
- Source non-mutation verification

### TRM Fractal Spine
- Structural oracle with refinement and state transition
- 1024-dimensional structural state space
- Corpus generation and schema validation

### Darwinian Matrix
- Episode lifecycle: genotype → phenotype → selection → reproduction
- Climate response system with state tracking
- Ecology engine with deterministic transactions
- Ledger with episode archive and replay

### Pipeline (P0 Control Protocol)
- One-child protocol with initial void scope
- Structural rollout with refinement validation
- Deterministic decoder with expansion contracts

### Runtime R0 (Deterministic Transaction)
- Receipt-bound transaction lifecycle
- Deterministic replay with SHA-256 binding
- Composition root with adapter injection

### Runtime R1 (Bounded Pre-Refinement Retrieval)
- HACF wrapper integration via FFI
- Evidence adapter with budget enforcement
- Query derivation with retrieval materialization

## Data flow

```
RequestContext
  → Runtime R0 transaction (receipt-bound)
  → Runtime R1 retrieval (bounded HACF)
  → Evidence adapter → projection compiler
  → Grid81 generation 000001 → StructuralOracle
  → Deterministic adjudication
  → Darwinian episode controller
  → Decoder + AST validation
  → Immutable receipt
```

## Design principles

1. **Determinism first** — all structural operations produce reproducible output
2. **Receipt-bound execution** — every transaction produces a verifiable receipt
3. **Canonical promotion gates** — components advance through qualified states
4. **Fail-closed** — unknown inputs produce explicit rejection, not silent defaults
5. **No runtime admission** — structural core operates without model execution
