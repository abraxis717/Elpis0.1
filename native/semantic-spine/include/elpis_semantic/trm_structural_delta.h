/* elpis_semantic/trm_structural_delta.h — Categorical structural delta v1.
 *
 * Delta is categorical Grid81 transition record. NOT numeric digit subtraction.
 * NOT residual81. NOT host direction.
 * Identity domain: "elpis.semantic.trm_structural_delta.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_STRUCTURAL_DELTA_H
#define ELPIS_SEMANTIC_TRM_STRUCTURAL_DELTA_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_STRUCTURAL_DELTA_VERSION 1u

/* Delta scope */
typedef enum trm_delta_scope {
    TRM_DELTA_MODEL_CANDIDATE = 0u,
    TRM_DELTA_GUARD_ADMITTED = 1u,
    TRM_DELTA_COMMITTED_STATE = 2u,
    TRM_DELTA_FIXTURE_INITIAL_TO_FINAL = 3u,
} trm_delta_scope;

/* Transition classes */
typedef enum trm_transition_class {
    TRM_TRANSITION_UNCHANGED_EMPTY = 0u,
    TRM_TRANSITION_UNCHANGED_FIXED_CORRECT = 1u,
    TRM_TRANSITION_UNCHANGED_WRITABLE_CORRECT = 2u,
    TRM_TRANSITION_UNCHANGED_WRITABLE_WRONG = 3u,
    TRM_TRANSITION_EMPTY_TO_CORRECT = 4u,
    TRM_TRANSITION_EMPTY_TO_WRONG = 5u,
    TRM_TRANSITION_WRONG_TO_CORRECT = 6u,
    TRM_TRANSITION_CORRECT_TO_WRONG = 7u,
    TRM_TRANSITION_WRONG_TO_DIFFERENT_WRONG = 8u,
    TRM_TRANSITION_BLOCKED_FIXED_CELL = 9u,
    TRM_TRANSITION_CANDIDATE_REJECTED = 10u,
    TRM_TRANSITION_INVALID_BLOCKED = 11u,
    TRM_TRANSITION_COUNT = 12u,
} trm_transition_class;

typedef struct elpis_semantic_trm_structural_delta_v1 {
    uint32_t                          abi_version;
    uint32_t                          delta_scope;
    uint32_t                          step_index;

    /* Digests */
    hacf_digest                       fixture_digest;
    hacf_digest                       model_manifest_digest;
    hacf_digest                       source_state_digest;
    hacf_digest                       candidate_frame_digest;
    hacf_digest                       target_state_digest;

    /* Digit arrays */
    uint32_t                          before_digits[GRID81_CELL_COUNT];
    uint32_t                          after_digits[GRID81_CELL_COUNT];
    uint32_t                          reference_digits[GRID81_CELL_COUNT];

    /* Masks */
    uint32_t                          changed_mask[GRID81_CELL_COUNT];
    uint32_t                          correct_before_mask[GRID81_CELL_COUNT];
    uint32_t                          correct_after_mask[GRID81_CELL_COUNT];
    uint32_t                          wrong_before_mask[GRID81_CELL_COUNT];
    uint32_t                          wrong_after_mask[GRID81_CELL_COUNT];

    /* Per-cell transition class */
    uint32_t                          transition_class[GRID81_CELL_COUNT];

    /* Aggregate counts */
    uint32_t                          changed_cell_count;
    uint32_t                          correct_addition_count;
    uint32_t                          wrong_addition_count;
    uint32_t                          correction_count;
    uint32_t                          regression_count;
    uint32_t                          wrong_to_different_wrong_count;
    uint32_t                          unchanged_correct_count;
    uint32_t                          unchanged_wrong_count;
    uint32_t                          unchanged_empty_count;
    int32_t                           net_correct_gain;
    int32_t                           wrong_cell_delta;

    /* Digest */
    hacf_digest                       structural_delta_digest;

    uint8_t                           reserved[64];
} elpis_semantic_trm_structural_delta_v1;

void elpis_trm_structural_delta_init(
    elpis_semantic_trm_structural_delta_v1 *delta);

/* Compute categorical structural delta.
 * Returns 0 on success. */
int elpis_trm_structural_delta_compute(
    elpis_semantic_trm_structural_delta_v1 *delta,
    const uint32_t before[GRID81_CELL_COUNT],
    const uint32_t after[GRID81_CELL_COUNT],
    const uint32_t reference[GRID81_CELL_COUNT],
    const uint32_t fixed_mask[GRID81_CELL_COUNT],
    trm_delta_scope scope,
    uint32_t step_index);

int elpis_trm_structural_delta_identity(
    const elpis_semantic_trm_structural_delta_v1 *delta,
    hacf_digest *out);

int elpis_trm_structural_delta_validate(
    const elpis_semantic_trm_structural_delta_v1 *delta);

int elpis_write_trm_structural_delta(const char *path,
    const elpis_semantic_trm_structural_delta_v1 *delta);
int elpis_read_trm_structural_delta(const char *path,
    elpis_semantic_trm_structural_delta_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
