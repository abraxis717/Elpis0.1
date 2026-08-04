/* elpis_semantic/trm_candidate_decode.h — Deterministic candidate decoder v1.
 *
 * Decodes TRM candidate-output frames into digit arrays. Supports
 * scores, probabilities, one-hot, and class-index formats.
 *
 * Class zero = NO_CHANGE for writable cells.
 */
#ifndef ELPIS_SEMANTIC_TRM_CANDIDATE_DECODE_H
#define ELPIS_SEMANTIC_TRM_CANDIDATE_DECODE_H

#include "elpis_semantic/grid81_policy.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Forward declaration — avoid full header dependency */
struct elpis_semantic_trm_candidate_frame_v1;

/* Decode scores/probabilities: argmax per cell, lowest-class tiebreak. */
int elpis_trm_decode_scores(
    const struct elpis_semantic_trm_candidate_frame_v1 *frame,
    uint32_t candidate_digits[GRID81_CELL_COUNT],
    uint32_t candidate_digit_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT]);

/* Decode one-hot output: extract single active class per cell. */
int elpis_trm_decode_one_hot(
    const struct elpis_semantic_trm_candidate_frame_v1 *frame,
    uint32_t candidate_digits[GRID81_CELL_COUNT],
    uint32_t candidate_digit_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT]);

/* Decode class-index output: direct copy with range check. */
int elpis_trm_decode_indices(
    const struct elpis_semantic_trm_candidate_frame_v1 *frame,
    uint32_t candidate_digits[GRID81_CELL_COUNT],
    uint32_t candidate_digit_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT]);

/* Unified decoder: dispatch based on candidate kind. */
int elpis_trm_candidate_decode(
    const struct elpis_semantic_trm_candidate_frame_v1 *frame,
    uint32_t candidate_digits[GRID81_CELL_COUNT],
    uint32_t candidate_digit_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT]);

#ifdef __cplusplus
}
#endif
#endif
