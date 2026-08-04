# Semantic Structural Spine V1

## 1. Closure Status

- **Version**: Semantic Structural Spine V1
- **Closure disposition**: `SEMANTIC_HYPERGRAPH_P13_INTEGRATED_STRUCTURAL_SPINE_VALIDATION_QUALIFIED`
- **Status**: CLOSED AND SEALED
- **Runtime admission**: FALSE

This document describes the architecture as sealed by P13. It does not describe a
system under construction.

## 2. System Purpose

The Semantic Structural Spine maps semantic hypergraph structure through a
deterministic compilation pipeline into Grid81 structural placement, applies
guarded structural refinement via a deterministic search backend, and produces
verifiable structural observations with full sidecar traceability.

It provides:
- Immutable semantic identity and relation tracking.
- Deterministic topology compilation.
- Deterministic Grid81 structural placement.
- Guarded structural refinement with fail-closed semantics.
- Full traceability via structural observation sidecar.

It does NOT provide:
- Runtime admission.
- Query service or response generation.
- Semantic interpretation from Sudoku digits.
- Autonomous semantic mutation.

## 3. Canonical Dataflow

```
P5 bounded semantic view
  ↓
P6 typed semantic topology
  ↓
P7 deterministic Grid81 structural packet
  ↓
P8 fixed/writable masks and candidate-frame ABI
  ↓
DETERMINISTIC_MRV_SOLVER proposal
  ↓
P8 decoder
  ↓
P9 state-bound guard
  ↓
guarded committed structural state
  ↓
trace-sidecar structural observation
```

## 4. Semantic Plane

The semantic plane (P0-P4 substrate, P5 bounded view) provides:

- **Semantic nodes**: Immutable identity-bearing entities.
- **Semantic hyperedges**: Multi-way relations between semantic nodes.
- **Incidences**: The incidence relationship between nodes and hyperedges.
- **Assertions**: Typed claims anchored to semantic entities with provenance.
- **Provenance**: Origin tracking for every semantic element.
- **Conflicts**: Detected contradictions between semantic assertions.
- **Bridges**: Connections between semantic domains or retrieval contexts.
- **Context requirements**: Dependencies on external context for semantic completeness.
- **Bounded semantic views**: Context-aware subsets of the full semantic graph, constructed by P5.
- **Immutable semantic identities**: Once assigned, semantic identities do not change.

Embeddings are a metric field over semantic objects. Retrieval is conditional
external context acquisition. Neither embeddings nor retrieval create semantic truth.

Semantic authority (identity, relation, provenance, conflicts) resides in P5/P6.
No downstream component may alter semantic identity or invent/lose relations.

## 5. Topology Compilation

P6 (Semantic Topology Compiler) responsibilities:

- Construct **topology vertices** from bounded semantic view.
- Derive **constraints** from semantic relations.
- Identify **constellations** — groups of semantically related topology vertices.
- Assign **lanes** — structural channels through which topology flows.
- Establish **affiliations** — vertex membership in constellations.
- Track **conflicts** — incompatible structural assignments.
- Record **bridges** — cross-domain topology connections.
- Generate **deterministic topology addresses** — canonical, replayable vertex identifiers.
- Ensure **relation-preserving compilation** — no semantic relation is lost in topology translation.

P6 does NOT assign Sudoku digits. Digit assignment is P7's responsibility.
P6 topology is relation-preserving but operates at a different abstraction level
than Grid81 placement.

## 6. Grid81 Structural Compilation

P7 (Grid81 Structural Compiler) responsibilities:

- **Deterministic placement**: Each topology vertex maps to a deterministic cell.
- **Canonical Sudoku template**: Standard 9x9 Sudoku structural constraint space.
- **Cell assignment**: Mapping from topology vertex to (row, col, digit).
- **Occupied-state construction**: Binary occupancy grid reflecting placed vertices.
- **Structural packet**: Canonical output containing placement, masks, and traceability data.
- **Sidecar traceability**: Parallel record linking each Grid81 cell to its topology source.

Architecture principle: **The graph assigns the task; the Sudoku assigns the shape.**

The Grid81 board alone is not lossless. The board plus sidecar provides structural
traceability. Grid81 digits are structural values — they carry no semantic meaning
and are not semantic labels.

## 7. Mutability and Guard Boundary

P8 and P9 together form the mutation control boundary:

### P8 — Mutability Policy and Candidate-Frame ABI

- **Fixed-cell policy**: Certain cells are immutable; their values cannot change.
- **Writable-cell policy**: Cells eligible for refinement are explicitly enumerated.
- **Candidate-frame ABI**: Typed interface for structural refinement proposals.
- **Numeric-only model/backend input**: The backend sees only board state, masks, and numeric data — never semantic sidecar.
- **Decoder**: Translates backend proposal into structural operations.

### P9 — State-Bound Guard and Bounded Execution

- **State-bound guard**: Every proposed change is validated against Sudoku constraints and fixed-cell policy.
- **Atomic Sudoku validity**: Each committed step preserves full board validity.
- **Fail-closed behavior**: If guard validation fails, the change is rejected; no partial commit occurs.
- **Bounded termination**: Execution terminates after a maximum step count.

The backend remains **proposal-only**. It never directly commits authoritative state.
All changes flow through P8 decoder and P9 guard.

## 8. Canonical Structural Refiner

**Name**: DETERMINISTIC_MRV_SOLVER
**Class**: DETERMINISTIC_SEARCH_REFINER
**Status**: ACTIVE_CANONICAL

Selection source: P11 replacement bakeoff
Integration source: P12 replacement-engine integration
Closure source: P13 structural-spine validation

MRV (Minimum Remaining Values) operates as follows:

- Consumes numeric board state and fixed/writable masks.
- Does NOT consume semantic sidecar data.
- Does NOT consume benchmark reference solutions.
- Does NOT alter semantic identity.
- Does NOT directly commit authoritative state.
- Proposals must pass through P8 decoder and P9 guard.

MRV is a deterministic search algorithm, not a learned TRM. It should not be
described as a learned model or renamed TRM.

## 9. Structural Observation and Sidecar

The trace sidecar records structural observations:
- Which cell was modified.
- What value was proposed and committed.
- Which topology vertex the cell corresponds to.
- Guard validation result.

The sidecar preserves traceability without creating semantic meaning. It is an
observational artifact, not a semantic authority. Sidecar round-trip is verified
by P13.

## 10. Authority Model

| Concern | Authority |
|---------|-----------|
| Semantic identity, relation, provenance, topology | P5 / P6 |
| Grid81 placement | P7 |
| Candidate proposal | DETERMINISTIC_MRV_SOLVER (proposal-only) |
| Candidate ABI, decoder, fixed/writable policy | P8 |
| State-bound guard, bounded termination | P9 |
| Canonical backend selection | P12 registry |
| Closure and consumption boundary | P13 |
| Application runtime admission | No current component — FALSE |

## 11. Determinism and Persistence

- Whole-spine deterministic replay: PASS (verified by P13)
- Fresh-process reproducibility: PASS
- ASan + UBSan: PASS
- 27/27 mandatory tests PASS
- P0-P12 nonregression: PASS

## 12. Historical Model Retirement

**ACTV1_Inner**

- Historical role: Frozen learned refinement candidate.
- P10 result: Measured not efficacious (valid measurement; structurally mixed; measured not efficacious).
- P10R diagnosis: Intrinsic model insufficiency confirmed.
- Current status: RETIRED_NEGATIVE_CONTROL
- Selectable: FALSE

ACTV1 evidence remains canonical history. The negative result is preserved without
minimization. ACTV1 is not part of the active spine.

## 13. Phase History

| Phase | Disposition | Primary Outcome | Current Consequence | Evidence Root |
|-------|-------------|-----------------|---------------------|---------------|
| P0 | QUALIFIED | Immutable hypergraph substrate | Qualified dependency | `reports/P0ImmutableHypergraph/` |
| P1 | QUALIFIED | Embedding references established | Qualified dependency | `reports/P1EmbeddingReferences/` |
| P2 | BLOCKED → QUALIFIED (P2R) | Context deficit detection; persistence fix | Qualified dependency | `reports/P2ContextDeficit/`, `reports/P2ContextDeficitRemediation/` |
| P3 | QUALIFIED | R3 retrieval bridge | Qualified dependency | `reports/P3R3RetrievalBridge/` |
| P4 | QUALIFIED (P4Q) | Evidence typing and admission; qualification confirmed | Qualified dependency | `reports/P4QualificationReconciliation/` |
| P5 | QUALIFIED | Context reevaluation and bounded semantic view | Active — spine entry point | `reports/P5ContextReevaluationBoundedView/` |
| P6 | QUALIFIED | Semantic topology compiler | Active — topology authority | `reports/P6SemanticTopologyCompiler/` |
| P7 | QUALIFIED | Grid81 structural compiler | Active — placement authority | `reports/P7Grid81StructuralCompiler/` |
| P8 | QUALIFIED | TRM adapter and mutability policy | Active — mutation control | `reports/P8TRMAdapterMutability/` |
| P9 | QUALIFIED | Frozen TRM execution and bounded refinement | Active — guard authority | `reports/P9FrozenTRMExecution/` |
| P10 | MEASURED_NOT_EFFICACIOUS | Valid measurement; structurally mixed; not efficacious | ACTV1 retired | `reports/P10GuardedRefinementEfficacy/` |
| P10R | INTRINSIC_INSUFFICIENCY_CONFIRMED | Intrinsic model insufficiency confirmed | ACTV1 non-selectable | `reports/P10RPlacementABIAlignment/` |
| P11 | QUALIFIED | Replacement bakeoff; DETERMINISTIC_MRV_SOLVER selected | Canonical backend chosen | `reports/P11RefinementEngineBakeoff/` |
| P12 | QUALIFIED | Replacement engine integration | DETERMINISTIC_MRV_SOLVER active | `reports/P12ReplacementEngineIntegration/` |
| P13 | QUALIFIED | Integrated structural spine validation; spine sealed | CLOSED AND SEALED | `reports/P13IntegratedStructuralSpine/` |

## 14. Verified Capabilities

- Immutable semantic hypergraph
- Embedding references
- Context-deficit detection
- R3 retrieval bridge
- Evidence typing and admission
- Bounded semantic view
- Deterministic semantic topology
- Deterministic Grid81 compilation
- Fixed/writable partition
- Guarded candidate execution
- Deterministic structural refinement
- Sidecar round-trip
- Whole-spine deterministic replay
- Sanitizer qualification (ASan + UBSan)
- Nonregression qualification (P0-P12)
- Closed evidence manifests (17 artifacts)

## 15. Explicit Non-Capabilities

V1 does NOT qualify:

- Application runtime admission
- User-facing query service
- Response generation
- Unrestricted online retrieval
- DarwinianMatrix orchestration
- Learned projector
- `residual81`
- Host-direction generation
- Semantic interpretation from Sudoku digits
- Autonomous semantic mutation
- Production deployment
- Monitoring and recovery
- Distributed execution
- GPU execution

## 16. Consumption Contract

Downstream programs may consume this spine as a **read-only dependency**. The
machine-readable manifest at `manifests/SEMANTIC_STRUCTURAL_SPINE_V1_MANIFEST.json`
provides exact digests for verification.

Changes to canonical bytes, identities, behavior, policy, or qualification evidence
require a new version (V2 or explicit successor). V1 remains immutable.

## 17. Evidence Index

See the machine-readable manifest for exact SHA-256 digests. Report roots:

- `reports/P0ImmutableHypergraph/P0_FINAL_REPORT.json`
- `reports/P1EmbeddingReferences/P1_FINAL_REPORT.json`
- `reports/P2ContextDeficitRemediation/P2R_FINAL_REPORT.json`
- `reports/P3R3RetrievalBridge/P3_FINAL_REPORT.json`
- `reports/P4QualificationReconciliation/P4Q_FINAL_REPORT.json`
- `reports/P5ContextReevaluationBoundedView/P5_FINAL_REPORT.json`
- `reports/P6SemanticTopologyCompiler/P6_FINAL_REPORT.json`
- `reports/P7Grid81StructuralCompiler/P7_FINAL_REPORT.json`
- `reports/P8TRMAdapterMutability/P8_FINAL_REPORT.json`
- `reports/P9FrozenTRMExecution/P9_FINAL_REPORT.json`
- `reports/P10GuardedRefinementEfficacy/P10_FINAL_REPORT.json`
- `reports/P10RPlacementABIAlignment/P10R_FINAL_REPORT.json`
- `reports/P11RefinementEngineBakeoff/P11_FINAL_REPORT.json`
- `reports/P12ReplacementEngineIntegration/P12_FINAL_REPORT.json`
- `reports/P13IntegratedStructuralSpine/P13_FINAL_REPORT.json`
