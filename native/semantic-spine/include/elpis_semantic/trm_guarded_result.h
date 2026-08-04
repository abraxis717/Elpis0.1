/* elpis_semantic/trm_guarded_result.h — Guarded TRM result packet v1.
 *
 * Final atomic result: either the guarded board (accepted) or the
 * exact original P7 input (rejected). Carries complete provenance
 * and disposition.
 *
 * Identity domain: "elpis.semantic.trm_guarded_result.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_GUARDED_RESULT_H
#define ELPIS_SEMANTIC_TRM_GUARDED_RESULT_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_GUARDED_RESULT_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Guarded result disposition                                               */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum trm_guarded_result_disposition {
    TRM_GUARDED_PROPOSAL_ACCEPTED              = 0u,
    TRM_GUARDED_PROPOSAL_ACCEPTED_NO_CHANGE    = 1u,
    TRM_GUARDED_PROPOSAL_REJECTED_FRAME_INVALID = 2u,
    TRM_GUARDED_PROPOSAL_REJECTED_SUDOKU_INVALID = 3u,
    TRM_GUARDED_PROPOSAL_REJECTED_POLICY       = 4u,
    TRM_GUARDED_PROPOSAL_BLOCKED_INTERNAL      = 5u,
} trm_guarded_result_disposition;

/* ──────────────────────────────────────────────────────────────────── */
/* Guarded result packet                                                    */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_trm_guarded_result_v1 {
    uint32_t                          abi_version;

    /* Provenance */
    hacf_digest                       adapter_packet_digest;
    hacf_digest                       candidate_frame_digest;
    hacf_digest                       candidate_decode_receipt_digest;
    hacf_digest                       output_guard_policy_digest;

    /* Digit digests */
    hacf_digest                       input_digit_array_digest;
    hacf_digest                       candidate_digit_array_digest;
    hacf_digest                       guarded_digit_array_digest;
    hacf_digest                       guarded_digit_class_tensor_digest;

    /* Mask digests */
    hacf_digest                       fixed_mask_digest;
    hacf_digest                       writable_mask_digest;
    hacf_digest                       candidate_changed_mask_digest;
    hacf_digest                       admitted_changed_mask_digest;
    hacf_digest                       fixed_violation_attempt_mask_digest;

    /* Counts */
    uint32_t                          candidate_changed_cell_count;
    uint32_t                          admitted_changed_cell_count;
    uint32_t                          fixed_violation_attempt_count;

    /* Sudoku validation */
    hacf_digest                       Sudoku_validation_receipt_digest;

    /* Disposition */
    uint32_t                          guard_disposition;

    /* Result identity */
    hacf_digest                       guarded_result_digest;
    hacf_digest                       HACF_package_digest;

    uint8_t                           reserved[64];
} elpis_semantic_trm_guarded_result_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                             */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize: set ABI version, zero reserved. */
void elpis_trm_guarded_result_init(
    elpis_semantic_trm_guarded_result_v1 *result);

/* Construct guarded result from guard output and Sudoku validation.
 * Returns disposition. */
int elpis_trm_guarded_result_construct(
    elpis_semantic_trm_guarded_result_v1 *result,
    const uint32_t input_digits[GRID81_CELL_COUNT],
    const uint32_t guarded_digits[GRID81_CELL_COUNT],
    const uint32_t candidate_changed_mask[GRID81_CELL_COUNT],
    const uint32_t admitted_changed_mask[GRID81_CELL_COUNT],
    const uint32_t fixed_violation_mask[GRID81_CELL_COUNT],
    uint32_t candidate_changed_count,
    uint32_t admitted_changed_count,
    uint32_t fixed_violation_count,
    int sudoku_valid,
    const hacf_digest *adapter_packet_digest,
    const hacf_digest *candidate_frame_digest,
    const hacf_digest *candidate_decode_receipt_digest,
    const hacf_digest *output_guard_policy_digest,
    const hacf_digest *input_digit_array_digest,
    const hacf_digest *candidate_digit_array_digest,
    const hacf_digest *fixed_mask_digest,
    const hacf_digest *writable_mask_digest,
    const hacf_digest *candidate_changed_mask_digest,
    const hacf_digest *admitted_changed_mask_digest,
    const hacf_digest *fixed_violation_mask_digest);

/* Compute result identity. Domain: "elpis.semantic.trm_guarded_result.v1" */
int elpis_trm_guarded_result_identity(
    const elpis_semantic_trm_guarded_result_v1 *result, hacf_digest *out);

/* Validate: disposition valid, invariants hold. */
int elpis_trm_guarded_result_validate(
    const elpis_semantic_trm_guarded_result_v1 *result);

/* Persistence */
int elpis_write_trm_guarded_result(const char *path,
    const elpis_semantic_trm_guarded_result_v1 *result);
int elpis_read_trm_guarded_result(const char *path,
    elpis_semantic_trm_guarded_result_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
