/* elpis_semantic/trm_step_metrics.h — Per-step evaluation metrics v1.
 *
 * Captures model candidate, guard outcome, and committed state for one step.
 * Identity domain: "elpis.semantic.trm_step_metrics.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_STEP_METRICS_H
#define ELPIS_SEMANTIC_TRM_STEP_METRICS_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_STEP_METRICS_VERSION 1u

typedef enum trm_step_disposition {
    TRM_STEP_COMMITTED_NO_CHANGE = 0u,
    TRM_STEP_COMMITTED_CHANGED = 1u,
    TRM_STEP_REJECTED_GUARD = 2u,
    TRM_STEP_REJECTED_SUDOKU_INVALID = 3u,
    TRM_STEP_REJECTED_CYCLE = 4u,
    TRM_STEP_EXECUTION_FAILURE = 5u,
} trm_step_disposition;

typedef struct elpis_semantic_trm_step_metrics_v1 {
    uint32_t                          abi_version;
    uint32_t                          step_index;

    /* Input state digest */
    hacf_digest                       input_state_digest;

    /* Model candidate */
    hacf_digest                       candidate_frame_digest;
    uint32_t                          candidate_changed_cells;

    /* Guard outcome */
    uint32_t                          admitted_changed_cells;
    uint32_t                          fixed_cell_violation_attempts;
    uint32_t                          guard_disposition;
    uint32_t                          sudoku_disposition;

    /* Committed state */
    hacf_digest                       committed_state_digest;
    uint32_t                          step_disposition; /* trm_step_disposition */

    /* Structural metrics */
    uint32_t                          correct_additions;
    uint32_t                          wrong_additions;
    uint32_t                          corrections;
    uint32_t                          regressions;

    /* Candidate vs admitted separation */
    uint32_t                          candidate_correct_additions;
    uint32_t                          candidate_wrong_additions;
    uint32_t                          candidate_corrections;
    uint32_t                          candidate_regressions;

    uint8_t                           reserved[64];
} elpis_semantic_trm_step_metrics_v1;

void elpis_trm_step_metrics_init(
    elpis_semantic_trm_step_metrics_v1 *metrics);

int elpis_trm_step_metrics_validate(
    const elpis_semantic_trm_step_metrics_v1 *metrics);

int elpis_write_trm_step_metrics(const char *path,
    const elpis_semantic_trm_step_metrics_v1 *metrics);
int elpis_read_trm_step_metrics(const char *path,
    elpis_semantic_trm_step_metrics_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
