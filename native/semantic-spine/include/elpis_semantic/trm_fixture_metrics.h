/* elpis_semantic/trm_fixture_metrics.h — Per-fixture evaluation metrics v1.
 *
 * Aggregates step metrics for a single fixture across all lanes.
 * Identity domain: "elpis.semantic.trm_fixture_metrics.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_FIXTURE_METRICS_H
#define ELPIS_SEMANTIC_TRM_FIXTURE_METRICS_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_FIXTURE_METRICS_VERSION 1u

typedef enum trm_fixture_verdict {
    TRM_FIXTURE_EXACTLY_SOLVED = 0u,
    TRM_FIXTURE_POSITIVE_IMPROVEMENT = 1u,
    TRM_FIXTURE_NO_CHANGE = 2u,
    TRM_FIXTURE_NEGATIVE_REGRESSION = 3u,
    TRM_FIXTURE_WRONG_FINAL_STATE = 4u,
    TRM_FIXTURE_EXECUTION_FAILURE = 5u,
    TRM_FIXTURE_EVALUATION_INVALID = 6u,
} trm_fixture_verdict;

typedef struct elpis_semantic_trm_fixture_metrics_v1 {
    uint32_t                          abi_version;
    uint32_t                          fixture_ordinal;

    /* Fixture identity */
    hacf_digest                       fixture_digest;
    uint32_t                          clue_stratum;
    uint32_t                          clue_count;

    /* Initial state */
    uint32_t                          initial_filled_cells;
    uint32_t                          initial_correct_cells;

    /* No-op lane */
    uint32_t                          noop_final_correct_cells;

    /* One-step lane */
    uint32_t                          onestep_final_correct_cells;
    uint32_t                          onestep_final_wrong_cells;
    int32_t                           onestep_net_correct_gain;

    /* Bounded lane */
    uint32_t                          bounded_final_correct_cells;
    uint32_t                          bounded_final_wrong_cells;
    uint32_t                          bounded_final_empty_cells;
    int32_t                           bounded_net_correct_gain;
    uint32_t                          bounded_sudoku_valid;

    /* Counts */
    uint32_t                          model_invocation_count;
    uint32_t                          committed_step_count;
    uint32_t                          rejected_step_count;
    uint32_t                          total_candidate_changes;
    uint32_t                          total_admitted_changes;
    uint32_t                          total_correct_additions;
    uint32_t                          total_wrong_additions;
    uint32_t                          total_corrections;
    uint32_t                          total_regressions;
    uint32_t                          total_fixed_violation_attempts;

    /* Completion */
    uint32_t                          exact_solution_achieved;
    uint32_t                          termination_reason_code;

    /* Bounded vs one-step comparison */
    int32_t                           bounded_vs_one_step_gain;

    /* Verdict */
    uint32_t                          fixture_verdict; /* trm_fixture_verdict */

    uint8_t                           reserved[64];
} elpis_semantic_trm_fixture_metrics_v1;

void elpis_trm_fixture_metrics_init(
    elpis_semantic_trm_fixture_metrics_v1 *metrics);

int elpis_trm_fixture_metrics_validate(
    const elpis_semantic_trm_fixture_metrics_v1 *metrics);

int elpis_write_trm_fixture_metrics(const char *path,
    const elpis_semantic_trm_fixture_metrics_v1 *metrics);
int elpis_read_trm_fixture_metrics(const char *path,
    elpis_semantic_trm_fixture_metrics_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
