# Elpis Semantic Fabric

## Status

**Semantic Structural Spine V1: CLOSED AND SEALED**

Closure disposition: `SEMANTIC_HYPERGRAPH_P13_INTEGRATED_STRUCTURAL_SPINE_VALIDATION_QUALIFIED`
Runtime admission: **FALSE**

## What This Repository Contains

The Elpis Semantic Fabric implements a **Semantic Structural Spine** — a deterministic
pipeline that maps semantic hypergraph structure through topology compilation into
Grid81 structural placement, applies guarded structural refinement via a deterministic
search backend, and produces verifiable structural observations with full sidecar
traceability.

This spine is closed. No further construction phases are planned under Semantic Fabric V1.

## Canonical Structural Spine

The active dataflow:

```
P5 bounded semantic view
  -> P6 semantic topology compiler
  -> P7 Grid81 structural compiler
  -> P8 mutability and candidate-frame boundary
  -> P12 DETERMINISTIC_MRV_SOLVER
  -> P8/P9 guarded bounded commit
  -> structural observation and sidecar traceability
```

In plain terms:

- The graph assigns the task.
- The Sudoku topology assigns the structural shape.
- The deterministic MRV backend proposes structural refinement.
- P8/P9 control mutation and commit.
- The sidecar preserves traceability without creating semantic meaning.

## Active Components

| Component | Role | Status |
|-----------|------|--------|
| P5 bounded semantic view | Semantic identity and bounded-view authority | ACTIVE |
| P6 semantic topology compiler | Semantic-to-topology compilation authority | ACTIVE |
| P7 Grid81 structural compiler | Structural placement authority | ACTIVE |
| P8 TRM adapter / mutability policy | Fixed/writable mask policy, candidate ABI, decoder authority | ACTIVE |
| P9 frozen TRM execution / bounded refinement | State-bound guard, bounded termination, fail-closed execution | ACTIVE |
| DETERMINISTIC_MRV_SOLVER (DETERMINISTIC_SEARCH_REFINER) | Canonical structural-refinement backend | ACTIVE_CANONICAL |

## Retired Components

| Component | Role | Status | Reason |
|-----------|------|--------|--------|
| ACTV1_Inner | Frozen learned refinement candidate | RETIRED_NEGATIVE_CONTROL | P10: measured not efficacious; P10R: intrinsic model insufficiency confirmed |

ACTV1_Inner is not selectable. It is not an active refiner. Its evidence remains
canonical historical record.

## Authority Boundaries

- **Semantic identity, relation, provenance, topology**: P5 / P6
- **Grid81 placement**: P7
- **Candidate proposal**: DETERMINISTIC_MRV_SOLVER (proposal-only; no authority)
- **Candidate ABI, decoder, fixed/writable policy**: P8
- **State-bound guard, bounded termination**: P9
- **Canonical backend selection**: P12 registry
- **Closure and consumption boundary**: P13
- **Application runtime admission**: No current component — admission is FALSE

### Grid81 and semantic authority

**Grid81 digits are structural values, not semantic labels.**

The final Grid81 board is not the semantic state. Semantic identities, relations,
provenance, conflicts, and authority remain owned by the semantic graph and topology
artifacts. The board alone is lossy; the board plus sidecar provides structural
traceability.

## Evidence and Verification

All phases P0-P13 have sealed evidence packages under `reports/`. Each contains a
final report and a raw evidence manifest with SHA-256 digests.

The machine-readable consolidation manifest is at:
`manifests/SEMANTIC_STRUCTURAL_SPINE_V1_MANIFEST.json`

## Runtime Status

Runtime admission: **FALSE**

This spine is a structural computation artifact. It does not constitute a runtime
service, query endpoint, or production-deployable system. The next program
(Elpis Runtime Integration) is a separate effort.

## Closed Scope

Semantic Structural Spine V1 scope is closed by P13. Bugfixes that change canonical
bytes, identities, behavior, policy, or qualification evidence require a new version
(V2 or explicit successor). Historical negative results (P10, P10R) remain attached
to V1.

## Downstream Consumption

Downstream programs may:
- Read the closure manifest.
- Bind the sealed spine as a read-only dependency.
- Submit valid qualified inputs and consume structural observations.
- Verify receipts and digests.

Downstream programs may NOT:
- Modify sealed P0-P13 evidence.
- Reactivate ACTV1_Inner.
- Bypass P8/P9 guards.
- Infer semantic meaning from Grid81 digits.
- Silently alter backend selection or ABI version.
- Claim runtime admission based on spine closure.

See `docs/SEMANTIC_STRUCTURAL_SPINE_V1_BOUNDARIES.md` for the full boundary specification.

## Canonical Documents

1. [Architecture: Semantic Structural Spine V1](docs/SEMANTIC_STRUCTURAL_SPINE_V1.md)
2. [Boundaries](docs/SEMANTIC_STRUCTURAL_SPINE_V1_BOUNDARIES.md)
3. [Next Program: Elpis Runtime Integration](docs/SEMANTIC_STRUCTURAL_SPINE_V1_NEXT_PROGRAM.md)
4. [Machine-Readable Manifest](manifests/SEMANTIC_STRUCTURAL_SPINE_V1_MANIFEST.json)
