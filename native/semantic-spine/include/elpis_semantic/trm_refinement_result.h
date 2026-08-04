/* trm_refinement_result.h — Bounded refinement result v1.
 *
 * Identity domain: "elpis.semantic.trm_refinement_result.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_REFINEMENT_RESULT_H
#define ELPIS_SEMANTIC_TRM_REFINEMENT_RESULT_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_REFINEMENT_RESULT_VERSION 1u

/* Termination reason codes */
typedef enum trm_termination_reason {
    TRM_TERMINATION_NO_MUTABLE_CELLS = 0u,
    TRM_TERMINATION_QUIESCENT_NO_CHANGE = 1u,
    TRM_TERMINATION_SUDOKU_COMPLETE = 2u,
    TRM_TERMINATION_CYCLE_DETECTED = 3u,
    TRM_TERMINATION_MAXIMUM_STEPS_REACHED = 4u,
    TRM_TERMINATION_GUARD_REJECTED = 5u,
    TRM_TERMINATION_EXECUTION_FAILED = 6u,
    TRM_TERMINATION_FRAME_INVALID = 7u,
    TRM_TERMINATION_INTERNAL_BLOCK = 8u,
} trm_termination_reason;

/* Boundedness receipt */
typedef struct trm_boundedness_receipt {
    uint8_t                           bounded;              /* always 1 */
    uint8_t                           no_convergence_claim; /* 1 when max_steps or cycle */
    uint8_t                           fail_closed;          /* 1 for guard_rejected/exec_failed */
    uint8_t                           reserved[59];
} trm_boundedness_receipt;

typedef struct elpis_semantic_trm_refinement_result_v1 {
    uint32_t                          abi_version;

    /* Identity bindings */
    hacf_digest                       root_P7_structural_packet_digest;
    hacf_digest                       root_P8_adapter_packet_digest;
    hacf_digest                       model_manifest_digest;
    hacf_digest                       runtime_policy_digest;
    hacf_digest                       refinement_policy_digest;
    hacf_digest                       refinement_trace_digest;

    /* Final state */
    hacf_digest                       final_state_digest;
    uint32_t                          final_grid81_digits[GRID81_CELL_COUNT];

    /* Summary */
    uint32_t                          model_invocation_count;
    uint32_t                          step_count;
    uint32_t                          committed_change_step_count;
    uint32_t                          total_admitted_changed_cells;
    uint32_t                          total_fixed_violation_attempts;
    uint32_t                          final_filled_cells;

    /* Termination */
    uint32_t                          termination_reason;   /* trm_termination_reason */
    trm_boundedness_receipt           boundedness_receipt;

    /* HACF */
    hacf_digest                       HACF_package_digest;

    /* Result identity */
    hacf_digest                       refinement_result_digest;

    /* Reserved */
    uint8_t                           reserved[64];
} elpis_semantic_trm_refinement_result_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_trm_refinement_result_init(
    elpis_semantic_trm_refinement_result_v1 *result);

/* Compute result identity. Domain: "elpis.semantic.trm_refinement_result.v1" */
int elpis_trm_refinement_result_identity(
    const elpis_semantic_trm_refinement_result_v1 *result, hacf_digest *out);

/* Validate: termination reason valid, final state matches trace,
 * boundedness correct, reserved zeroed. */
int elpis_trm_refinement_result_validate(
    const elpis_semantic_trm_refinement_result_v1 *result);

/* Persistence */
int elpis_write_trm_refinement_result(const char *path,
    const elpis_semantic_trm_refinement_result_v1 *result);
int elpis_read_trm_refinement_result(const char *path,
    elpis_semantic_trm_refinement_result_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
