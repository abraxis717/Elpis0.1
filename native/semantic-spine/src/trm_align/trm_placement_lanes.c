#include "elpis_semantic/trm_alignment_lane.h"
#include "elpis_semantic/trm_alignment_fixture.h"
#include <string.h>

/* Forward declaration from trm_representation_lanes.c */
extern int trm_representation_lane_validate(const trm_lane_result_t *result);

/* Placement lane: validate placement results.
 * Model execution happens in Python; C validates placement consistency. */

int trm_placement_lane_validate(const trm_lane_result_t *result) {
    return trm_representation_lane_validate(result);
}

int trm_placement_lane_compare(const trm_lane_result_t *native,
                                const trm_lane_result_t *p7_style) {
    if (!native || !p7_style) return 0;
    return trm_lane_compare(p7_style, native);
}
