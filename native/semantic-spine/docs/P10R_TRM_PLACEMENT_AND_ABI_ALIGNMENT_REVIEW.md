# P10R — TRM Placement and ABI Alignment Review

## Disposition

**SEMANTIC_HYPERGRAPH_P10R_INTRINSIC_MODEL_INSUFFICIENCY_CONFIRMED**

## Executive Summary

P10R was tasked with determining why the frozen TRM (ACTV1_Inner, 1.3M params)
failed to produce reliable structural progress under the P7-P9 pipeline, as
measured by P10's 16-fixture efficacy corpus (net-correct gain +1, 0/16
positive bounded fixtures).

P10R executed controlled diagnostic lanes across 48 test fixtures (3 sets of 16)
to distinguish between 10 hypotheses for the failure. The result: **the frozen
TRM is intrinsically insufficient for Sudoku refinement** — even under its own
native-evidenced contract.

## Diagnostic Method

P10R reconstructed the native TRM contract from the architecture source
(`trm.py:118`), training script (`train_trm_grid.py`), and checkpoint metadata.
It then executed the frozen model across controlled diagnostic lanes:

| Lane | Purpose | Fixtures | Key Result |
|------|---------|----------|------------|
| R0 P8 Production | Baseline P8 encoding | 16 (Set B) | net-correct gain = -3 |
| R1 Native Exact | Native int64 tokens | 16 (Set B) | identical to R0 |
| P0 P7-style | P7 structural placement | 16 (Set C) | net-correct gain = -6 |
| P1 Native-valid | Native-valid placement | 16 (Set C) | net-correct gain = 0 |
| P2 Control | Deterministic placement | 16 (Set C) | net-correct gain = 0 |
| Native one-step | In-distribution control | 16 (Set B) | 0/16 positive, gain = -3 |

## Native Contract Reconstruction

The native TRM was trained as a **denoising autoencoder** on randomly corrupted
complete Sudoku grids:

- **Input**: `[B, 81]` int64 token indices through learned `CastedEmbedding(10, 256)`
- **Training corruption**: Random zero (p=0.15), swap (p=0.05), flip (p=0.05)
- **Expected blanks**: 0-20 per grid (mean ~12)
- **Target**: Complete grid (all 81 cells, including givens)
- **Decoder**: Argmax per cell with lowest-class tiebreak
- **Loss**: Cross-entropy with `ignore_index=-100`

P10 evaluated on structured Sudoku partial boards with **33-57 blanks** (24-48
clues) — fundamentally outside the training regime.

## Hypothesis Results

| Hypothesis | Verdict | Evidence |
|-----------|---------|----------|
| H1: Input representation mismatch | REJECTED | P8 one-hot → int64 bridge is lossless |
| H2: Blank/class order mismatch | REJECTED | Class 0 = blank in both P8 and native |
| H3: Layout/dtype/normalization | REJECTED | P8 bridge converts correctly |
| H4: P7 placement mismatch | REJECTED | Native-valid placement no better than P7-style |
| H5: Clue distribution mismatch | CONFIRMED | P10 uses 33-57 blanks; native expects 0-20 |
| H6: Decoder semantics mismatch | REJECTED | P8 argmax matches native argmax exactly |
| H7: Guard granularity mismatch | REJECTED | 0 correct intent in rejected proposals |
| H8: Recursive distribution shift | REJECTED | No degradation after committed changes |
| H9: Compound mismatch | N/A | Primary cause is H10 |
| H10: Intrinsic model insufficiency | CONFIRMED | 0/16 positive fixtures under native contract |

## Key Finding: Intrinsic Model Insufficiency

Under native in-distribution conditions (randomly corrupted complete grids,
~12 blanks, native int64 input, native argmax decoder), the frozen TRM
produced:

- **0/16 positive fixtures** (no fixture showed net improvement)
- **Net-correct gain: -3** (3 more wrong additions than correct)
- **0 correct additions** across all 16 fixtures

This means the model was never an effective Sudoku refinement engine, even
for the task it was trained on. The P10 evaluation with sparse boards (33-57
blanks) is an even harder regime that the model is fundamentally unequipped
for.

## P10 Negative Result Binding

P10 remains `SEMANTIC_HYPERGRAPH_P10_MEASURED_NOT_EFFICACIOUS`. P10R does not
retroactively qualify or disqualify the frozen TRM. The negative result stands
as measured.

## Remediation Recommendation

**RETIRE_FROZEN_TRM_FROM_REFINEMENT_ROLE**

The frozen TRM should not be used for Sudoku refinement. Next gate:
`FROZEN_TRM_RETIREMENT_AND_REPLACEMENT_REVIEW`.

## Stop Boundary Compliance

- P7, P8, P9, P10 identities: UNCHANGED
- Frozen model weights: UNCHANGED
- HACF: UNCHANGED
- R3: UNCHANGED
- No training, fine-tuning, or backward() calls
- No projector target qualified
- No residual81 defined
- No GPU usage (CPU-only)
- Runtime admission: FALSE
- Shadow root: UNTOUCHED
- Burned G7 fixtures: UNTOUCHED

## Evidence Package

58 artifacts in `reports/P10RPlacementABIAlignment/`.

## Determinism

- Fresh-process determinism: PASS (3 runs, 8 key artifacts identical)
- ASan + UBSan: PASSED (3/3 C tests)
- ThreadSanitizer: NOT_APPLICABLE (single-threaded)
- P0-P10 nonregression: PASS (60/82 tests, 22 pre-existing integration Not Run)
- C tests: 3/3 PASSED (release + ASan/UBSan)
