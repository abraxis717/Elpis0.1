# P10 — Guarded Refinement Efficacy and Structural Delta

## Disposition

**SEMANTIC_HYPERGRAPH_P10_MEASURED_NOT_EFFICACIOUS**

Measurement evidence is complete and valid. Structural-delta corpus qualifies.
Model verdict is STRUCTURALLY_MIXED. This is a valid scientific result, not an infrastructure failure.

## Summary

P10 measured whether the qualified frozen TRM (P9) produces useful structural
progress on Sudoku refinement under guarded bounded recursion.

### Key Results

- **16/16 fixtures** generated and executed across 4 clue strata (24, 32, 40, 48)
- **16/16 unique reference solutions** verified by deterministic solver
- **1/16 fixtures** showed any committed structural change (fixture 11, stratum 40)
- **15/16 fixtures** terminated with NO_CHANGE — model produced only quiescent proposals
- **0 fixtures** showed positive improvement; **0 showed regression**
- **1 fixture** ended in WRONG_FINAL_STATE (correct addition + wrong addition, net gain 0)
- **Aggregate bounded net-correct gain: 1** (one correct addition, one wrong addition)
- **38 fixed-cell violation attempts** blocked by guard (guard is functional)
- **10 guard rejections** (Sudoku-invalid committed states rejected)
- **Aggregate correct cells: 581** (one above no-op baseline of 580)

### Verdict: STRUCTURALLY_MIXED

The frozen TRM shows marginal structural signal: one correct addition across
the full corpus, but also one wrong addition. The aggregate gain is positive
(>0) but no stratum shows consistent improvement. This fails the pre-registered
efficacy thresholds (minimum 8 positive fixtures, zero wrong final cells) but
produces a valid, measurable result.

## Architecture

```
qualified P9 frozen execution -> sealed P10 corpus -> three-lane execution
    -> categorical structural deltas -> efficacy adjudication -> handoff
```

P10 owns: evaluation corpus, reference solutions, structural deltas, efficacy
metrics, verdict, and downstream handoff. P10 does NOT alter P7-P9 artifacts,
train the model, or grant runtime admission.

## Source Layout

- `include/elpis_semantic/trm_*.h` — P10 header ABI (9 headers)
- `src/trm_eval/*.c` — P10 C implementation (7 sources)
- `tools/trm_eval/run_p10_corpus.py` — Full evaluation engine
- `tests/trm_eval/*.c` — P10 C tests (4 targets, pass under ASan+UBSan)
- `reports/P10GuardedRefinementEfficacy/` — 47 evidence artifacts

## Efficacy Thresholds (Pre-registered)

- Minimum positive fixtures: 8 (actual: 0) — FAIL
- Maximum negative fixtures: 0 (actual: 0) — PASS
- Maximum wrong final cells: 0 (actual: 1) — FAIL
- Minimum aggregate net-correct gain > 0 (actual: 1) — PASS
- Each stratum improved: (actual: none) — FAIL
- Bounded not worse than one-step: PASS
- Beats no-op baseline: PASS

## Structural Delta ABI

Categorical Grid81 transitions. NOT numeric digit subtraction. NOT residual81.
Candidate, admitted, and committed deltas remain distinct.

Transition classes: UNCHANGED_EMPTY, UNCHANGED_FIXED_CORRECT,
UNCHANGED_WRITABLE_CORRECT, EMPTY_TO_CORRECT, EMPTY_TO_WRONG,
WRONG_TO_CORRECT, CORRECT_TO_WRONG, WRONG_TO_DIFFERENT_WRONG.

## P9 Production Witness

Analyzed separately. 1 model invocation, 1 admitted change, 4 guard rejections.
Uses canonical-template agreement terminology (not unique-solution correctness).

## Nonregression

- P0-P9 identities unchanged (verified by digest)
- Frozen model unchanged (1,316,354 parameters, digest verified)
- HACF, R3, shadow root untouched
- No training, optimizer, backward pass, or projector
- Runtime admission: FALSE

## Next Action

SEMANTIC_HYPERGRAPH_P10_REMEDIATION_OR_TRM_PLACEMENT_REVIEW
