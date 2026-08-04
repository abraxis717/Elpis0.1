#include "elpis_semantic/trm_alignment_lane.h"
#include "elpis_semantic/trm_alignment_fixture.h"
#include <string.h>

/* Representation lane: execute a single fixture through a representation transform.
 * The model execution happens in Python; C validates results. */

int trm_representation_lane_validate(const trm_lane_result_t *result) {
    if (!result) return 0;
    if (result->changed_cell_count > TRM_DECODED_CELL_COUNT) return 0;
    if (result->correct_additions < 0 || result->wrong_additions < 0) return 0;
    if (result->class_zero_frequency < 0.0f || result->class_zero_frequency > 1.0f) return 0;
    return 1;
}
