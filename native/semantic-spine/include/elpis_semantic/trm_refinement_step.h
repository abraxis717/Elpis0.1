/* trm_refinement_step.h — Single refinement step v1.
 *
 * Identity domain: "elpis.semantic.trm_refinement_step.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_REFINEMENT_STEP_H
#define ELPIS_SEMANTIC_TRM_REFINEMENT_STEP_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_REFINEMENT_STEP_VERSION 1u

/* Step disposition codes */
typedef enum trm_step_disposition {
    STEP_COMMITTED_CHANGED = 0u,
    STEP_COMMITTED_NO_CHANGE = 1u,
    STEP_REJECTED_FRAME_INVALID = 2u,
    STEP_REJECTED_SUDOKU_INVALID = 3u,
    STEP_BLOCKED_EXECUTION_FAILURE = 4u,
    STEP_BLOCKED_POLICY = 5u,
    STEP_BLOCKED_INTERNAL = 6u,
} trm_step_disposition;

typedef struct elpis_semantic_trm_refinement_step_v1 {
    uint32_t                          abi_version;

    /* Step index */
    uint32_t                          step_index;

    /* Input state */
    hacf_digest                       input_state_digest;

    /* Execution */
    hacf_digest                       execution_request_digest;
    hacf_digest                       execution_receipt_digest;

    /* Candidate */
    hacf_digest                       candidate_frame_digest;
    hacf_digest                       candidate_decode_receipt_digest;

    /* Guard */
    hacf_digest                       state_guard_receipt_digest;
    hacf_digest                       candidate_state_digest_or_zero;
    hacf_digest                       committed_state_digest;

    /* Change tracking */
    uint32_t                          candidate_changed_cell_count;
    uint32_t                          admitted_changed_cell_count;
    uint32_t                          fixed_violation_attempt_count;

    /* Disposition */
    uint32_t                          step_disposition;    /* trm_step_disposition */

    /* Trace */
    hacf_digest                       step_trace_digest;

    /* Step identity */
    hacf_digest                       step_digest;

    /* Reserved */
    uint8_t                           reserved[64];
} elpis_semantic_trm_refinement_step_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_trm_refinement_step_init(
    elpis_semantic_trm_refinement_step_v1 *step);

/* Compute step identity. Domain: "elpis.semantic.trm_refinement_step.v1" */
int elpis_trm_refinement_step_identity(
    const elpis_semantic_trm_refinement_step_v1 *step, hacf_digest *out);

/* Validate: digests present, disposition valid,
 * committed_state only for COMMITTED dispositions, reserved zeroed. */
int elpis_trm_refinement_step_validate(
    const elpis_semantic_trm_refinement_step_v1 *step);

/* Persistence */
int elpis_write_trm_refinement_step(const char *path,
    const elpis_semantic_trm_refinement_step_v1 *step);
int elpis_read_trm_refinement_step(const char *path,
    elpis_semantic_trm_refinement_step_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
