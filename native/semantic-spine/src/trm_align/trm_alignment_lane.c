#include "elpis_semantic/trm_alignment_lane.h"
#include <string.h>

trm_lane_result_t trm_lane_result_create(const char *lane_id) {
    trm_lane_result_t result;
    memset(&result, 0, sizeof(result));
    strncpy(result.lane_id, lane_id, sizeof(result.lane_id) - 1);
    result.logits_digest[0] = '\0';
    return result;
}

int trm_lane_result_compute_metrics(trm_lane_result_t *result,
                                     const int8_t decoded[TRM_DECODED_CELL_COUNT],
                                     const int8_t input[TRM_FIXTURE_CELL_COUNT],
                                     const int8_t fixed_mask[TRM_FIXTURE_CELL_COUNT],
                                     const int8_t solution[TRM_FIXTURE_CELL_COUNT]) {
    if (!result || !decoded || !input || !fixed_mask || !solution) return 0;

    int correct = 0, wrong = 0, fixed_violations = 0;
    int changed_count = 0, blank_count = 0, final_correct = 0, final_wrong = 0;
    int class_zero_count = 0;

    // Build proposal with fixed cells enforced
    int8_t proposal[TRM_DECODED_CELL_COUNT];
    memcpy(proposal, decoded, sizeof(proposal));
    for (int i = 0; i < TRM_DECODED_CELL_COUNT; i++) {
        if (fixed_mask[i] == 1) proposal[i] = input[i];
    }

    for (int i = 0; i < TRM_DECODED_CELL_COUNT; i++) {
        if (fixed_mask[i] == 0 && decoded[i] != input[i]) {
            changed_count++;
            result->changed_cells[changed_count - 1] = (int8_t)i;
            if (decoded[i] == solution[i]) correct++;
            else if (decoded[i] != 0) wrong++;
        }
        if (fixed_mask[i] == 1 && decoded[i] != input[i]) fixed_violations++;
        if (decoded[i] == 0) class_zero_count++;

        // Final metrics on admitted proposal
        if (proposal[i] == solution[i]) final_correct++;
        if (proposal[i] != 0 && proposal[i] != solution[i]) final_wrong++;
        if (proposal[i] == 0) blank_count++;
    }

    result->changed_cell_count = (uint32_t)changed_count;
    result->correct_additions = correct;
    result->wrong_additions = wrong;
    result->fixed_violations = fixed_violations;
    result->net_correct_gain = correct - wrong;
    result->final_correct = final_correct;
    result->final_wrong = final_wrong;
    result->final_blank = blank_count;
    result->class_zero_frequency = (float)class_zero_count / (float)TRM_DECODED_CELL_COUNT;

    // Sudoku validation for guard
    int valid = 1;
    // Check rows
    for (int r = 0; r < 9 && valid; r++) {
        int seen[10] = {0};
        for (int c = 0; c < 9 && valid; c++) {
            int d = proposal[r * 9 + c];
            if (d == 0) continue;
            if (d < 1 || d > 9 || seen[d]) { valid = 0; break; }
            seen[d] = 1;
        }
    }
    if (valid) {
        for (int c = 0; c < 9 && valid; c++) {
            int seen[10] = {0};
            for (int r = 0; r < 9 && valid; r++) {
                int d = proposal[r * 9 + c];
                if (d == 0) continue;
                if (seen[d]) { valid = 0; break; }
                seen[d] = 1;
            }
        }
    }
    if (valid) {
        for (int br = 0; br < 3 && valid; br++) {
            for (int bc = 0; bc < 3 && valid; bc++) {
                int seen[10] = {0};
                for (int r = br * 3; r < (br + 1) * 3 && valid; r++) {
                    for (int c = bc * 3; c < (bc + 1) * 3 && valid; c++) {
                        int d = proposal[r * 9 + c];
                        if (d == 0) continue;
                        if (seen[d]) { valid = 0; break; }
                        seen[d] = 1;
                    }
                }
            }
        }
    }
    result->guard_admitted = valid;
    result->sudoku_valid = valid;

    return 1;
}

int trm_lane_compare(const trm_lane_result_t *a, const trm_lane_result_t *b) {
    if (!a || !b) return 0;
    // Return 1 if b materially outperforms a (2x net gain threshold)
    int32_t baseline = a->net_correct_gain > 0 ? a->net_correct_gain : 1;
    return (b->net_correct_gain > 2 * baseline) ? 1 : 0;
}
