/* elpis_semantic/refiner_metrics.h — Per-candidate metrics v1.
 *
 * Identity domain: "elpis.semantic.refiner_metrics.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINER_METRICS_H
#define ELPIS_SEMANTIC_REFINER_METRICS_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINER_METRICS_VERSION 1u

typedef struct elpis_semantic_refiner_metrics_v1 {
    uint32_t                          abi_version;
    uint32_t                          positive_bounded_fixtures;
    uint32_t                          no_change_bounded_fixtures;
    uint32_t                          negative_bounded_fixtures;
    uint32_t                          wrong_final_state_fixtures;
    uint32_t                          exactly_solved_fixtures;
    uint32_t                          aggregate_noop_correct_cells;
    uint32_t                          aggregate_bounded_correct_cells;
    int32_t                           aggregate_bounded_net_correct_gain;
    uint32_t                          total_correct_additions;
    uint32_t                          total_wrong_additions;
    uint32_t                          total_corrections;
    uint32_t                          total_regressions;
    uint32_t                          total_candidate_changes;
    uint32_t                          total_admitted_changes;
    uint32_t                          guard_rejection_count;
    uint32_t                          execution_failure_count;
    uint32_t                          model_invocation_count;
    uint32_t                          committed_step_count;
    hacf_digest                       metrics_digest;
    uint8_t                           reserved[64];
} elpis_semantic_refiner_metrics_v1;

void elpis_refiner_metrics_init(elpis_semantic_refiner_metrics_v1 *m);
int elpis_refiner_metrics_identity(const elpis_semantic_refiner_metrics_v1 *m,
    hacf_digest *out);
int elpis_refiner_metrics_validate(const elpis_semantic_refiner_metrics_v1 *m);

int elpis_write_refiner_metrics(const char *path,
    const elpis_semantic_refiner_metrics_v1 *m);
int elpis_read_refiner_metrics(const char *path,
    elpis_semantic_refiner_metrics_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
