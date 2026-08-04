#include "elpis_semantic/trm_alignment_metrics.h"
#include <string.h>

trm_aggregate_metrics_t trm_metrics_aggregate(const trm_lane_result_t *results, uint32_t count) {
    trm_aggregate_metrics_t agg;
    memset(&agg, 0, sizeof(agg));
    agg.fixture_count = count;
    if (!results || count == 0) return agg;

    for (uint32_t i = 0; i < count; i++) {
        agg.total_correct_additions += results[i].correct_additions;
        agg.total_wrong_additions += results[i].wrong_additions;
        agg.total_fixed_violations += results[i].fixed_violations;
        agg.total_candidate_changes += results[i].changed_cell_count;
        agg.guard_admitted_count += results[i].guard_admitted;
        agg.positive_fixtures += (results[i].net_correct_gain > 0) ? 1 : 0;
        agg.no_change_fixtures += (results[i].changed_cell_count == 0) ? 1 : 0;
        agg.average_class_zero_frequency += results[i].class_zero_frequency;
    }
    agg.net_correct_gain = agg.total_correct_additions - agg.total_wrong_additions;
    agg.guard_rejected_count = count - agg.guard_admitted_count;
    agg.average_class_zero_frequency /= (float)count;
    return agg;
}

int trm_metrics_materially_outperforms(const trm_aggregate_metrics_t *candidate,
                                        const trm_aggregate_metrics_t *baseline,
                                        float threshold) {
    if (!candidate || !baseline) return 0;
    int32_t baseline_gain = baseline->net_correct_gain > 0 ? baseline->net_correct_gain : 1;
    return (candidate->net_correct_gain > (int32_t)(threshold * baseline_gain));
}
