/* trm_candidate_decode.c — Deterministic candidate decoder v1. */

#include "elpis_semantic/trm_candidate_frame.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <math.h>
#include <string.h>
#include <stdint.h>

/* Decode scores/probabilities: argmax per cell, lowest-class tiebreak. */
int elpis_trm_decode_scores(
    const elpis_semantic_trm_candidate_frame_v1 *frame,
    uint32_t candidate_digits[GRID81_CELL_COUNT],
    uint32_t candidate_digit_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT])
{
    if (!frame || !candidate_digits || !candidate_digit_classes) return SEMANTIC_E_INVAL;
    if (frame->candidate_kind != TRM_OUTPUT_DIGIT_CLASS_SCORES &&
        frame->candidate_kind != TRM_OUTPUT_DIGIT_CLASS_PROBABILITIES) {
        return SEMANTIC_E_INVAL;
    }

    memset(candidate_digit_classes, 0, sizeof(uint32_t) * GRID81_CELL_COUNT * GRID81_DIGIT_CLASS_COUNT);

    for (uint32_t cell = 0; cell < GRID81_CELL_COUNT; cell++) {
        uint32_t best_class = 0;
        float best_val = frame->candidate[(size_t)cell * GRID81_DIGIT_CLASS_COUNT + 0];

        if (isnan(best_val) || isinf(best_val)) return SEMANTIC_E_INVAL;

        for (uint32_t cls = 1; cls < GRID81_DIGIT_CLASS_COUNT; cls++) {
            float v = frame->candidate[(size_t)cell * GRID81_DIGIT_CLASS_COUNT + cls];
            if (isnan(v) || isinf(v)) return SEMANTIC_E_INVAL;
            /* Strict greater-than: lowest-class wins on tie */
            if (v > best_val) {
                best_val = v;
                best_class = cls;
            }
        }

        candidate_digits[cell] = best_class;
        candidate_digit_classes[cell][best_class] = 1;
    }
    return SEMANTIC_OK;
}

/* Decode one-hot output: exactly one active class per cell. */
int elpis_trm_decode_one_hot(
    const elpis_semantic_trm_candidate_frame_v1 *frame,
    uint32_t candidate_digits[GRID81_CELL_COUNT],
    uint32_t candidate_digit_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT])
{
    if (!frame || !candidate_digits || !candidate_digit_classes) return SEMANTIC_E_INVAL;
    if (frame->candidate_kind != TRM_OUTPUT_DIGIT_CLASS_ONE_HOT) return SEMANTIC_E_INVAL;

    memset(candidate_digit_classes, 0, sizeof(uint32_t) * GRID81_CELL_COUNT * GRID81_DIGIT_CLASS_COUNT);

    for (uint32_t cell = 0; cell < GRID81_CELL_COUNT; cell++) {
        uint32_t active_class = 0;
        uint32_t active_count = 0;

        for (uint32_t cls = 0; cls < GRID81_DIGIT_CLASS_COUNT; cls++) {
            float v = frame->candidate[(size_t)cell * GRID81_DIGIT_CLASS_COUNT + cls];
            if (v == 1.0f) {
                active_count++;
                active_class = cls;
            } else if (v != 0.0f) {
                return SEMANTIC_E_INVAL;
            }
        }

        if (active_count != 1) return SEMANTIC_E_INVAL;

        candidate_digits[cell] = active_class;
        candidate_digit_classes[cell][active_class] = 1;
    }
    return SEMANTIC_OK;
}

/* Decode class-index output: direct copy. */
int elpis_trm_decode_indices(
    const elpis_semantic_trm_candidate_frame_v1 *frame,
    uint32_t candidate_digits[GRID81_CELL_COUNT],
    uint32_t candidate_digit_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT])
{
    if (!frame || !candidate_digits || !candidate_digit_classes) return SEMANTIC_E_INVAL;
    if (frame->candidate_kind != TRM_OUTPUT_DIGIT_CLASS_INDICES) return SEMANTIC_E_INVAL;

    memset(candidate_digit_classes, 0, sizeof(uint32_t) * GRID81_CELL_COUNT * GRID81_DIGIT_CLASS_COUNT);

    for (uint32_t cell = 0; cell < GRID81_CELL_COUNT; cell++) {
        int val = (int)frame->candidate[cell];
        if (val < 0 || val > 9) return SEMANTIC_E_INVAL;

        candidate_digits[cell] = (uint32_t)val;
        candidate_digit_classes[cell][val] = 1;
    }
    return SEMANTIC_OK;
}

/* Unified decoder: dispatch based on candidate kind. */
int elpis_trm_candidate_decode(
    const elpis_semantic_trm_candidate_frame_v1 *frame,
    uint32_t candidate_digits[GRID81_CELL_COUNT],
    uint32_t candidate_digit_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT])
{
    if (!frame) return SEMANTIC_E_INVAL;

    switch (frame->candidate_kind) {
        case TRM_OUTPUT_DIGIT_CLASS_SCORES:
        case TRM_OUTPUT_DIGIT_CLASS_PROBABILITIES:
            return elpis_trm_decode_scores(frame, candidate_digits, candidate_digit_classes);
        case TRM_OUTPUT_DIGIT_CLASS_ONE_HOT:
            return elpis_trm_decode_one_hot(frame, candidate_digits, candidate_digit_classes);
        case TRM_OUTPUT_DIGIT_CLASS_INDICES:
            return elpis_trm_decode_indices(frame, candidate_digits, candidate_digit_classes);
        default:
            return SEMANTIC_E_INVAL;
    }
}
