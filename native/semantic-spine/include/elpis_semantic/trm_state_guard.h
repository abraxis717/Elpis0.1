/* trm_state_guard.h — State-bound P8-equivalent guard v1.
 *
 * Applies P8 guard semantics against the current P9 recursive state
 * while retaining the original static masks. For use in steps after
 * step zero.
 *
 * Identity domain: "elpis.semantic.trm_state_guard.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_STATE_GUARD_H
#define ELPIS_SEMANTIC_TRM_STATE_GUARD_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_STATE_GUARD_VERSION 1u

typedef enum trm_state_guard_disposition {
    TRM_STATE_GUARD_ACCEPTED = 0u,
    TRM_STATE_GUARD_REJECTED_SUDOKU_INVALID = 1u,
    TRM_STATE_GUARD_BLOCKED_POLICY = 2u,
    TRM_STATE_GUARD_BLOCKED_INTERNAL = 3u,
} trm_state_guard_disposition;

typedef struct elpis_semantic_trm_state_guard_v1 {
    uint32_t                          abi_version;

    /* Binding digests */
    hacf_digest                       current_state_digest;
    hacf_digest                       candidate_frame_digest;
    hacf_digest                       static_fixed_mask_digest;
    hacf_digest                       static_writable_mask_digest;

    /* Guarded output digits */
    uint32_t                          guarded_digits[GRID81_CELL_COUNT];

    /* Change tracking */
    uint32_t                          candidate_changed_mask[GRID81_CELL_COUNT];
    uint32_t                          admitted_changed_mask[GRID81_CELL_COUNT];
    uint32_t                          fixed_violation_mask[GRID81_CELL_COUNT];

    /* Counts */
    uint32_t                          candidate_changed_cell_count;
    uint32_t                          admitted_changed_cell_count;
    uint32_t                          fixed_violation_attempt_count;

    /* Sudoku validation */
    int                               sudoku_valid;

    /* Disposition */
    uint32_t                          disposition;   /* trm_state_guard_disposition */

    /* Digests */
    hacf_digest                       candidate_changed_mask_digest;
    hacf_digest                       admitted_changed_mask_digest;
    hacf_digest                       fixed_violation_mask_digest;
    hacf_digest                       guarded_digit_array_digest;

    /* Guard identity */
    hacf_digest                       state_guard_digest;

    /* Reserved */
    uint8_t                           reserved[64];
} elpis_semantic_trm_state_guard_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_trm_state_guard_init(
    elpis_semantic_trm_state_guard_v1 *guard);

/* Apply state-bound guard:
 * - fixed cells preserved from original P7 givens
 * - writable cells: candidate 1-9 admitted, class 0 = no change from current state
 * - atomic Sudoku validation of complete guarded board
 * Returns disposition. */
int elpis_trm_state_guard_apply(
    elpis_semantic_trm_state_guard_v1 *guard,
    const uint32_t current_state_digits[GRID81_CELL_COUNT],
    const uint32_t original_P7_digits[GRID81_CELL_COUNT],
    const uint32_t static_fixed_mask[GRID81_CELL_COUNT],
    const uint32_t static_writable_mask[GRID81_CELL_COUNT],
    const uint32_t candidate_digits[GRID81_CELL_COUNT],
    const hacf_digest *current_state_digest,
    const hacf_digest *candidate_frame_digest,
    const hacf_digest *static_fixed_mask_digest,
    const hacf_digest *static_writable_mask_digest);

/* Compute guard identity. Domain: "elpis.semantic.trm_state_guard.v1" */
int elpis_trm_state_guard_identity(
    const elpis_semantic_trm_state_guard_v1 *guard, hacf_digest *out);

/* Validate: admitted changes zero on fixed cells, disposition valid,
 * reserved zeroed. */
int elpis_trm_state_guard_validate(
    const elpis_semantic_trm_state_guard_v1 *guard,
    const uint32_t static_fixed_mask[GRID81_CELL_COUNT]);

/* Persistence */
int elpis_write_trm_state_guard(const char *path,
    const elpis_semantic_trm_state_guard_v1 *guard);
int elpis_read_trm_state_guard(const char *path,
    elpis_semantic_trm_state_guard_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
