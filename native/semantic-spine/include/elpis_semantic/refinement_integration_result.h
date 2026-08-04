/* elpis_semantic/refinement_integration_result.h — Integration result v1.
 *
 * Immutable result from canonical refinement integration. Contains step trace,
 * committed states, and termination reason.
 *
 * Identity domain: "elpis.semantic.refinement_integration_result.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINEMENT_INTEGRATION_RESULT_H
#define ELPIS_SEMANTIC_REFINEMENT_INTEGRATION_RESULT_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINEMENT_INTEGRATION_RESULT_VERSION 1u
#define REFINEMENT_MAX_STEPS 16u
#define REFINEMENT_MAX_COMMITTED_STATES 16u

/* ──────────────────────────────────────────────────────────────────── */
/* Step disposition                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum refinement_step_disposition {
    INTEGRATION_STEP_COMMITTED_CHANGED    = 0u,
    INTEGRATION_STEP_COMMITTED_NO_CHANGE  = 1u,
    INTEGRATION_STEP_REJECTED_BY_GUARD    = 2u,
    INTEGRATION_STEP_BLOCKED_BY_BACKEND   = 3u,
    INTEGRATION_STEP_BLOCKED_BY_ADAPTER   = 4u,
    INTEGRATION_STEP_BLOCKED_BY_FRAME     = 5u,
    INTEGRATION_STEP_BLOCKED_INTERNAL     = 6u,
} refinement_step_disposition;

/* ──────────────────────────────────────────────────────────────────── */
/* Termination reason                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum refinement_termination_reason {
    INTEGRATION_TERMINATION_NO_MUTABLE_CELLS    = 0u,
    INTEGRATION_TERMINATION_QUIESCENT_NO_CHANGE = 1u,
    INTEGRATION_TERMINATION_SUDOKU_COMPLETE     = 2u,
    INTEGRATION_TERMINATION_CYCLE_DETECTED      = 3u,
    INTEGRATION_TERMINATION_MAXIMUM_STEPS       = 4u,
    INTEGRATION_TERMINATION_GUARD_REJECTED      = 5u,
    INTEGRATION_TERMINATION_BACKEND_FAILED      = 6u,
    INTEGRATION_TERMINATION_ADAPTER_FAILED      = 7u,
    INTEGRATION_TERMINATION_FRAME_INVALID       = 8u,
    INTEGRATION_TERMINATION_INTERNAL_BLOCK      = 9u,
} refinement_termination_reason;

/* ──────────────────────────────────────────────────────────────────── */
/* Step digest entry                                                          */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct refinement_step_digest_entry {
    uint32_t                          step_index;
    uint32_t                          disposition;   /* refinement_step_disposition */
    uint32_t                          admitted_changes;
    hacf_digest                       committed_state_digest;
} refinement_step_digest_entry;

/* ──────────────────────────────────────────────────────────────────── */
/* Integration result                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_refinement_integration_result_v1 {
    uint32_t                              abi_version;

    /* Identity bindings */
    hacf_digest                           integration_request_digest;
    hacf_digest                           backend_registry_digest;
    hacf_digest                           active_backend_digest;
    hacf_digest                           active_adapter_digest;
    hacf_digest                           integration_policy_digest;

    /* Ordered step digests */
    uint32_t                              step_count;
    refinement_step_digest_entry          ordered_steps[REFINEMENT_MAX_STEPS];

    /* Ordered committed state digests */
    uint32_t                              committed_state_count;
    hacf_digest                           ordered_committed_states[REFINEMENT_MAX_COMMITTED_STATES];

    /* Initial and final state */
    hacf_digest                           initial_state_digest;
    hacf_digest                           final_state_digest;
    uint32_t                              final_grid81_digits[GRID81_CELL_COUNT];

    /* Summary */
    uint32_t                              backend_invocation_count;
    uint32_t                              committed_change_step_count;
    uint32_t                              total_admitted_change_count;
    uint32_t                              fixed_violation_attempt_count;
    uint32_t                              termination_reason;  /* refinement_termination_reason */

    /* Boundedness */
    uint8_t                               execution_bounded;
    uint8_t                               fail_closed;
    uint8_t                               all_sudoku_valid;
    uint8_t                               fixed_clues_unchanged;

    /* HACF */
    hacf_digest                           HACF_package_digest;

    /* Result identity digest */
    hacf_digest                           integration_result_digest;

    uint8_t                               reserved[128];
} elpis_semantic_refinement_integration_result_v1;

/* Initialize */
void elpis_refinement_integration_result_init(
    elpis_semantic_refinement_integration_result_v1 *result);

/* Compute result identity. Domain: "elpis.semantic.refinement_integration_result.v1" */
int elpis_refinement_integration_result_identity(
    const elpis_semantic_refinement_integration_result_v1 *result, hacf_digest *out);

/* Validate: ABI version, step dispositions valid, states Sudoku-valid, reserved zeroed. */
int elpis_refinement_integration_result_validate(
    const elpis_semantic_refinement_integration_result_v1 *result);

/* Persistence */
int elpis_write_refinement_integration_result(const char *path,
    const elpis_semantic_refinement_integration_result_v1 *result);
int elpis_read_refinement_integration_result(const char *path,
    elpis_semantic_refinement_integration_result_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
