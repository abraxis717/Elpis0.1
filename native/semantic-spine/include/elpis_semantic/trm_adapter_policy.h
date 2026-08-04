/* elpis_semantic/trm_adapter_policy.h — Immutable TRM adapter policy v1.
 *
 * Defines every behavioral rule that governs adaptation between P7 Grid81
 * structural data and the frozen TRM ABI. Changing any field creates a
 * new policy identity.
 *
 * Identity domain: "elpis.semantic.trm_adapter_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_ADAPTER_POLICY_H
#define ELPIS_SEMANTIC_TRM_ADAPTER_POLICY_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_ADAPTER_POLICY_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Policy enums                                                           */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum trm_input_conversion_policy {
    TRM_INPUT_CONVERSION_EXACT_ONE_HOT_TO_FLOAT32 = 0u,
} trm_input_conversion_policy;

typedef enum trm_fixed_cell_policy {
    TRM_FIXED_WHEN_NONZERO_OR_OCCUPIED = 0u,
} trm_fixed_cell_policy;

typedef enum trm_writable_cell_policy {
    TRM_WRITABLE_WHEN_ZERO_AND_UNOCCUPIED = 0u,
} trm_writable_cell_policy;

typedef enum trm_candidate_decode_policy {
    TRM_CANDIDATE_DECODE_ARGMAX_WITHOUT_SOFTMAX = 0u,
} trm_candidate_decode_policy;

typedef enum trm_tie_break_policy {
    TRM_TIE_BREAK_LOWEST_DIGIT_CLASS = 0u,
} trm_tie_break_policy;

typedef enum trm_nonfinite_output_policy {
    TRM_NONFINITE_REJECT_COMPLETE_FRAME = 0u,
} trm_nonfinite_output_policy;

typedef enum trm_class_zero_policy {
    TRM_CLASS_ZERO_NO_CHANGE_FOR_WRITABLE = 0u,
} trm_class_zero_policy;

typedef enum trm_proposal_application_policy {
    TRM_PROPOSAL_ATOMIC_COMPLETE_BOARD = 0u,
} trm_proposal_application_policy;

typedef enum trm_sudoku_validation_policy {
    TRM_SUDOKU_VALIDATION_REQUIRED = 0u,
} trm_sudoku_validation_policy;

typedef enum trm_invalid_proposal_policy {
    TRM_INVALID_RETURN_EXACT_INPUT_BOARD = 0u,
} trm_invalid_proposal_policy;

typedef enum trm_sidecar_isolation_policy {
    TRM_SIDECAR_ISOLATION_MODEL_INPUT_NUMERIC_ONLY = 0u,
} trm_sidecar_isolation_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* Policy flags                                                           */
/* ──────────────────────────────────────────────────────────────────── */

#define TRM_POLICY_FLAG_NONE       0u
#define TRM_POLICY_FLAG_STRICT     0x01u
#define TRM_POLICY_FLAG_MASK       0x01u

/* ──────────────────────────────────────────────────────────────────── */
/* Policy record                                                          */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_trm_adapter_policy_v1 {
    uint32_t                          abi_version;

    /* Digests of bound upstream artifacts */
    hacf_digest                       P7_grid81_abi_digest;
    hacf_digest                       TRM_abi_digest;

    /* Behavioral rules */
    uint32_t                          input_conversion_policy;
    uint32_t                          fixed_cell_policy;
    uint32_t                          writable_cell_policy;
    uint32_t                          candidate_decode_policy;
    uint32_t                          tie_break_policy;
    uint32_t                          nonfinite_output_policy;
    uint32_t                          class_zero_policy;
    uint32_t                          proposal_application_policy;
    uint32_t                          sudoku_validation_policy;
    uint32_t                          invalid_proposal_policy;
    uint32_t                          sidecar_isolation_policy;

    /* Capacity */
    uint32_t                          maximum_changed_cells;

    /* Flags and identity */
    uint32_t                          policy_flags;
    hacf_digest                       policy_digest;

    uint8_t                           reserved[64];
} elpis_semantic_trm_adapter_policy_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                             */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize with P8 v1 defaults. */
void elpis_trm_adapter_policy_init(
    elpis_semantic_trm_adapter_policy_v1 *policy);

/* Compute policy identity. Domain: "elpis.semantic.trm_adapter_policy.v1" */
int elpis_trm_adapter_policy_identity(
    const elpis_semantic_trm_adapter_policy_v1 *policy, hacf_digest *out);

/* Validate: ABI version, all enum values known, reserved zeroed, max_changed<=81. */
int elpis_trm_adapter_policy_validate(
    const elpis_semantic_trm_adapter_policy_v1 *policy);

/* Persistence */
int elpis_write_trm_adapter_policy(const char *path,
    const elpis_semantic_trm_adapter_policy_v1 *policy);
int elpis_read_trm_adapter_policy(const char *path,
    elpis_semantic_trm_adapter_policy_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
