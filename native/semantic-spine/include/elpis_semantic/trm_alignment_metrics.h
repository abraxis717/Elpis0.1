#ifndef ELPIS_SEMANTIC_TRM_ALIGNMENT_METRICS_H
#define ELPIS_SEMANTIC_TRM_ALIGNMENT_METRICS_H

#include <stdint.h>
#include "trm_alignment_lane.h"

typedef struct {
    uint32_t fixture_count;
    int32_t total_correct_additions;
    int32_t total_wrong_additions;
    int32_t net_correct_gain;
    int32_t total_fixed_violations;
    uint32_t total_candidate_changes;
    uint32_t guard_admitted_count;
    uint32_t guard_rejected_count;
    uint32_t positive_fixtures;
    uint32_t no_change_fixtures;
    float average_class_zero_frequency;
} trm_aggregate_metrics_t;

trm_aggregate_metrics_t trm_metrics_aggregate(const trm_lane_result_t *results, uint32_t count);
int trm_metrics_materially_outperforms(const trm_aggregate_metrics_t *candidate,
                                        const trm_aggregate_metrics_t *baseline,
                                        float threshold);

#endif
