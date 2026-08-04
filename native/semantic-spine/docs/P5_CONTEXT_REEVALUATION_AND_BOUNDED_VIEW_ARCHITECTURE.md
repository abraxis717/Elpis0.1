# P5 — Context Re-evaluation, Bounded Semantic View, and Downstream Handoff ABI

## Identity domain

`elpis.semantic.context_reevaluation.v1`

## Position in the pipeline

```
query overlay
  ↓
embedding references and metric neighborhoods (P1)
  ↓
initial P2 context-deficit evaluation (P2)
  ↓
P3 retrieval bridge (P3)
  ↓
P4 evidence typing and semantic admission (P4)
  ↓
P5 post-admission context re-evaluation (THIS PHASE)
  ├── RETRIEVAL_CONTINUATION_REQUIRED
  ├── CONTEXT_ITERATION_STOPPED
  └── CONTEXT_SUFFICIENT
      ↓
      bounded semantic view
      ↓
      downstream handoff packet
      ↓
      future semantic topology compiler (outside P5)
```

## Five core definitions

### 1. Typed-evidence view

The complete post-P4 semantic and provenance state. Contains admitted claims, admitted
relations, their assertions, evidence spans, source spans, and embedding collection
bindings. Consumable as a read-only index via `elpis_typed_evidence_view_v1`.

### 2. Context re-evaluation

The application of the qualified P2 requirement set to the new typed-evidence view.
P5 rebinds the original P2 requirements to the new view, invokes the P2 evaluator
unchanged, and preserves the exact P2 disposition.

### 3. Context iteration

One immutable retrieval-and-admission round within a bounded sequence. Round 0 is the
initial pre-retrieval P2 evaluation. Round N (N >= 1) represents the Nth P3 retrieval +
P4 admission + P5 re-evaluation cycle. P5 records whether another round is authorized
but does not execute rounds beyond round 1.

### 4. Bounded semantic view

A deterministic selected subview of sufficient semantic context, constructed only when
P2 returns `CONTEXT_SUFFICIENT` and P5 adjudicates
`CONTEXT_SUFFICIENT_AND_BOUNDED_VIEW_READY`. Contains four separate planes: semantic,
provenance, metric, and control.

### 5. Downstream handoff

An immutable ABI manifest intended for a later semantic topology compiler. Contains
plane digests, registry chains, payload dependency manifests, and typed feature records.
Not a Grid81 packet. Not a TRM input. Not a host direction.

## Authority boundaries

| Phase | Owns |
|-------|------|
| P0 | Immutable semantic hypergraph foundation |
| P1 | Embedding references and metric neighborhoods |
| P2 | **Context-sufficiency evaluation** (sole authority) |
| P3 | Retrieval transport |
| P4 | Typed semantic admission |
| P5 | **Iteration control and deterministic bounded-view construction** |

P5 does NOT own:
- Projection (future topology compiler)
- Grid81 cells or mapping
- TRM behavior
- Host actuation
- Evidence retrieval
- Embedding model execution
- Evidence typing
- Claim or relation admission
- Contradiction resolution
- Text generation

## Four planes of the bounded view

### Semantic plane
Admitted semantic nodes, hyperedges, and canonical incidences. Transport-only relations
remain distinguishable from semantic relations.

### Provenance plane
Assertions, P4 admission receipts, exact evidence spans, retrieval-item attachments,
RetrievalBundle references, source-document identities. Graph-edge provenance status
remains `UNAVAILABLE`.

### Metric plane
Embedding reference identities, embedding profile identities, vector-object identities,
deterministic integer score keys, neighborhood-view identities. Does NOT contain inferred
semantic relations.

### Control plane
Seed reasons, candidate origins, inclusion reasons, mandatory vs. optional status,
requirement mappings, rank tuples, conflict flags, scope/qualifier flags, omission
records, capacity diagnostics.

## Nondependency boundary

Reusable P5 source must not depend on: ACTV1, DimpleTransformer, model checkpoints,
tokenizers, generative models, Microsoft GraphRAG, Grid81, Sudoku, projectors, TRM,
StructuralOracle, StructuralRolloutController, DarwinianMatrix, ECRF, GPU execution,
network services, Python runtime, local model ports, machine-specific filesystem paths.

Public ABI remains C-compatible. C++ may be used internally where existing qualified
C++ interfaces require it.

## Iteration outcomes

P5 produces exactly one iteration outcome per round:

| Outcome | May produce bounded view? |
|---------|--------------------------|
| `CONTEXT_SUFFICIENT_AND_BOUNDED_VIEW_READY` | YES — only valid outcome |
| `RETRIEVAL_CONTINUATION_REQUIRED` | NO |
| `CONTEXT_ITERATION_STOPPED_NO_PROGRESS` | NO |
| `CONTEXT_ITERATION_STOPPED_ROUND_LIMIT` | NO |
| `CONTEXT_REEVALUATION_BLOCKED` | NO |
| `CONTEXT_REQUIREMENT_SET_INVALID` | NO |
| `BOUNDED_VIEW_BLOCKED_BY_CAPACITY` | NO |
| `BOUNDED_VIEW_BLOCKED_BY_INTEGRITY` | NO |

A stopped retrieval loop is NOT context sufficiency. Round limit is NOT context
sufficiency. P2 `EVALUATION_BLOCKED` never becomes sufficient. P2
`REQUIREMENT_SET_INVALID` never becomes sufficient.

## Default P5 v1 policy

```
maximum_retrieval_rounds: 3
maximum_stagnant_rounds: 1
identical retrieval-requirement bundle: STOP_NO_PROGRESS
identical typed-evidence-view digest: STOP_NO_PROGRESS
identical mandatory-deficit set with no contributing semantic delta: STOP_NO_PROGRESS
blocked evaluation: FAIL_CLOSED
invalid requirement set: FAIL_CLOSED
round limit reached with unresolved mandatory deficits: STOP_ROUND_LIMIT
```

## Default P5 v1 bounded-view limits

```
maximum_semantic_nodes: 256
maximum_semantic_hyperedges: 512
maximum_incidences: 2048
maximum_assertions: 1024
maximum_source_spans: 256
maximum_transport_references: 256
maximum_embedding_references: 256
maximum_metric_observations: 512
maximum_graph_hops: 2
maximum_metric_neighbors_per_seed: 8
```

## Overflow behavior

Mandatory closure overflow: `FAIL_CLOSED`.
Optional candidate overflow: deterministic omission of lower-ranked candidates, preserved
in omission manifest by identity and reason. Never silently drop a mandatory seed,
required participant, scope, qualifier, conflict counterpart, or provenance witness.

## Deterministic candidate ranking

Lexicographic priority tuple (no floating point):
1. Mandatory inclusion (mandatory before optional)
2. Candidate priority class (lower numeric first)
3. Requirement level (mandatory > preferred > diagnostic > none)
4. Origin class (mandatory_seed, required_participant, conflict_closure, scope_closure,
   qualifier_closure, semantic_graph_neighbor, provenance_witness, transport_witness,
   metric_supplement)
5. Semantic graph hop (lower first)
6. Effective authority (higher first)
7. Distinct qualifying provenance count (higher first)
8. Conflict preservation flag (counterparts before unrelated)
9. Metric score key (higher for similarity, lower for distance)
10. Semantic object digest (lexicographic)
11. Candidate record digest (lexicographic)

Raw floating-point embedding scores never control canonical order.
