# P11 — Refinement Engine Replacement Bakeoff

## Disposition

**SEMANTIC_HYPERGRAPH_P11_REFINEMENT_ENGINE_REPLACEMENT_QUALIFIED**

## Summary

P10 and P10R established that ACTV1_Inner (frozen TRM) is intrinsically insufficient for the structural-refinement role. P11 inventoried already-local executable candidates, implemented adapters, executed them over the sealed P10 corpus, and selected a qualified replacement.

## Candidates

| Candidate | Class | Disposition | Result |
|-----------|-------|-------------|--------|
| ACTV1_Inner | FROZEN_NEURAL_REFINER | RETIRED_NEGATIVE_CONTROL | Not eligible (P10R retirement) |
| DETERMINISTIC_MRV_SOLVER | DETERMINISTIC_RULE_REFINER | ADMISSIBLE | QUALIFIED — 16/16 positive fixtures |

## Winner

**DETERMINISTIC_MRV_SOLVER** — Constraint propagation engine (naked singles + hidden singles).

- Proposes only provably-correct placements
- No guessing, no reference-solution access, no semantic-sidecar access
- CPU-only, deterministic, no training
- 16/16 positive fixtures, 0 negative, 0 wrong final cells
- Aggregate bounded net-correct gain: 247
- All committed states Sudoku-valid
- Fixed clues unchanged across all fixtures

## Architecture

```
P10/P10R retired ACTV1_Inner evidence
  ↓
Local candidate inventory (Phase 1)
  ↓
Candidate eligibility filter (Phase 2)
  ↓
Candidate-specific numeric adapter (Phase 4)
  ↓
Common P8 candidate-frame ABI
  ↓
Common P8/P9 decoder and guard (Phase 5)
  ↓
Sealed P10 efficacy corpus (Phase 6)
  ↓
One-step and bounded bakeoff (Phase 6)
  ↓
Deterministic comparative ranking (Phase 8)
  ↓
Qualified replacement handoff (Phase 9)
```

## Source Layout

```
include/elpis_semantic/refiner_candidate.h    — Candidate identity
include/elpis_semantic/refiner_bakeoff_policy.h — Bakeoff policy
include/elpis_semantic/refiner_adapter.h        — Common adapter ABI
include/elpis_semantic/refiner_execution.h      — Execution transaction
include/elpis_semantic/refiner_metrics.h        — Per-candidate metrics
include/elpis_semantic/refiner_selection.h      — Qualification and ranking
include/elpis_semantic/refiner_handoff.h        — Replacement handoff

src/refiner/refiner_*.c                        — C implementations
src/refiner_candidates/                        — Candidate-specific adapters
tools/refiner/run_p11_bakeoff.py               — Authoritative bakeoff runner
tests/refiner/                                 — P11 test suite
reports/P11RefinementEngineBakeoff/            — Evidence package
```

## Evidence Package

18 files under `reports/P11RefinementEngineBakeoff/`:

- P11_INPUT_AUDIT.json
- P11_CANDIDATE_INVENTORY.json
- P11_CANDIDATE_MANIFESTS.json
- P11_BAKEOFF_POLICY.json
- P11_ADAPTER_CONFORMANCE.json
- P11_CORPUS_BINDING.json
- P11_EXECUTION_RESULTS.json
- P11_PER_CANDIDATE_METRICS.json
- P11_COMPARATIVE_REPORT.json
- P11_SELECTION_RESULT.json
- P11_REPLACEMENT_HANDOFF.json
- P11_TEST_RESULTS.json
- P11_SANITIZER_RESULTS.json
- P11_FRESH_PROCESS_DETERMINISM.json
- P11_NONREGRESSION.json
- P11_FINAL_REPORT.json
- P11_FINAL_PRINT.txt
- RAW_EVIDENCE_MANIFEST.json

## Qualification Thresholds (from P10)

- Minimum positive bounded fixtures: 8 of 16 ✓ (16)
- Maximum negative bounded fixtures: 0 ✓ (0)
- Maximum wrong final cells: 0 ✓ (0)
- Minimum aggregate net-correct gain: >0 ✓ (247)
- Each stratum improved: ≥1 ✓ (4,4,4,4)
- All committed states Sudoku-valid: ✓
- All fixed clues unchanged: ✓
- Deterministic replay: ✓
- Semantic sidecar isolation: ✓
- Reference-solution isolation: ✓
- Runtime admission: FALSE

## Stop Boundary

P11 does NOT begin replacement production integration. P11 does NOT modify P7-P10R artifacts. Next action: SEMANTIC_HYPERGRAPH_P12_REPLACEMENT_ENGINE_INTEGRATION.
