/* elpis_semantic/trm_output_guard.h — Fail-closed TRM output guard v1.
 *
 * Enforces fixed-cell immutability and confines candidate changes to
 * writable cells. Produces guarded digits and change masks.
 *
 * Identity domain: "elpis.semantic.trm_output_guard.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_OUTPUT_GUARD_H
#define ELPIS_SEMANTIC_TRM_OUTPUT_GUARD_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_OUTPUT_GUARD_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Guard disposition                                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum trm_guard_disposition {
    TRM_GUARD_CONTINUE_TO_SUDOKU_GATE = 0u,
    TRM_GUARD_REJECTED_POLICY         = 1u,
    TRM_GUARD_BLOCKED_INTERNAL        = 2u,
} trm_guard_disposition;

/* ──────────────────────────────────────────────────────────────────── */
/* Output guard record                                                      */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_trm_output_guard_v1 {
    uint32_t                          abi_version;

    /* Policy digest */
    hacf_digest                       output_guard_policy_digest;

    /* Input data digests */
    hacf_digest                       adapter_packet_digest;
    hacf_digest                       candidate_frame_digest;

    /* Guarded output */
    uint32_t                          guarded_digit[GRID81_CELL_COUNT];

    /* Change tracking */
    uint32_t                          candidate_changed_mask81[GRID81_CELL_COUNT];
    uint32_t                          admitted_changed_mask81[GRID81_CELL_COUNT];
    uint32_t                          fixed_cell_violation_attempt_mask81[GRID81_CELL_COUNT];

    /* Counts */
    uint32_t                          candidate_changed_cell_count;
    uint32_t                          admitted_changed_cell_count;
    uint32_t                          fixed_violation_attempt_count;

    /* Disposition */
    uint32_t                          disposition; /* trm_guard_disposition */

    /* Digests */
    hacf_digest                       candidate_changed_mask_digest;
    hacf_digest                       admitted_changed_mask_digest;
    hacf_digest                       fixed_violation_attempt_mask_digest;

    uint8_t                           reserved[64];
} elpis_semantic_trm_output_guard_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                             */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize: zero output and reserved. */
void elpis_trm_output_guard_init(
    elpis_semantic_trm_output_guard_v1 *guard);

/* Apply guard: enforce fixed-cell immutability, confine changes to writable cells.
 * Returns disposition. */
int elpis_trm_output_guard_apply(
    elpis_semantic_trm_output_guard_v1 *guard,
    const uint32_t input_digits[GRID81_CELL_COUNT],
    const uint32_t fixed_mask[GRID81_CELL_COUNT],
    const uint32_t writable_mask[GRID81_CELL_COUNT],
    const uint32_t candidate_digits[GRID81_CELL_COUNT],
    const hacf_digest *adapter_packet_digest,
    const hacf_digest *candidate_frame_digest);

/* Validate: admitted changes zero on fixed cells, disposition valid. */
int elpis_trm_output_guard_validate(
    const elpis_semantic_trm_output_guard_v1 *guard,
    const uint32_t fixed_mask[GRID81_CELL_COUNT]);

/* Persistence */
int elpis_write_trm_output_guard(const char *path,
    const elpis_semantic_trm_output_guard_v1 *guard);
int elpis_read_trm_output_guard(const char *path,
    elpis_semantic_trm_output_guard_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
