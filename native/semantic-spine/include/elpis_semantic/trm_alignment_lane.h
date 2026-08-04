#ifndef ELPIS_SEMANTIC_TRM_ALIGNMENT_LANE_H
#define ELPIS_SEMANTIC_TRM_ALIGNMENT_LANE_H

#include <stdint.h>
#include "trm_alignment_fixture.h"

#define TRM_LANE_RESULT_DIGEST_LEN 64
#define TRM_DECODED_CELL_COUNT 81
#define TRM_DIGIT_CLASS_COUNT 10

typedef struct {
    char lane_id[64];
    int8_t decoded_tokens[TRM_DECODED_CELL_COUNT];
    int8_t changed_cells[TRM_DECODED_CELL_COUNT];
    uint32_t changed_cell_count;
    int32_t correct_additions;
    int32_t wrong_additions;
    int32_t fixed_violations;
    int guard_admitted;
    int32_t net_correct_gain;
    int32_t final_correct;
    int32_t final_wrong;
    int32_t final_blank;
    float class_zero_frequency;
    float nonfinite_rate;
    int sudoku_valid;
    char logits_digest[TRM_LANE_RESULT_DIGEST_LEN];
} trm_lane_result_t;

trm_lane_result_t trm_lane_result_create(const char *lane_id);
int trm_lane_result_compute_metrics(trm_lane_result_t *result,
                                     const int8_t decoded[TRM_DECODED_CELL_COUNT],
                                     const int8_t input[TRM_FIXTURE_CELL_COUNT],
                                     const int8_t fixed_mask[TRM_FIXTURE_CELL_COUNT],
                                     const int8_t solution[TRM_FIXTURE_CELL_COUNT]);
int trm_lane_compare(const trm_lane_result_t *a, const trm_lane_result_t *b);

#endif
