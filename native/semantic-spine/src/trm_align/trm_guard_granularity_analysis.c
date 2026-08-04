#include "elpis_semantic/trm_guard_granularity_analysis.h"
#include "elpis_semantic/trm_alignment_fixture.h"
#include <string.h>

trm_guard_analysis_t trm_guard_analysis_create(uint32_t ordinal) {
    trm_guard_analysis_t analysis;
    memset(&analysis, 0, sizeof(analysis));
    analysis.fixture_ordinal = ordinal;
    return analysis;
}

void trm_guard_analyze_proposal(trm_guard_analysis_t *analysis,
                                  const int8_t decoded[TRM_DECODED_CELL_COUNT],
                                  const int8_t input[TRM_FIXTURE_CELL_COUNT],
                                  const int8_t fixed_mask[TRM_FIXTURE_CELL_COUNT],
                                  const int8_t solution[TRM_FIXTURE_CELL_COUNT]) {
    if (!analysis || !decoded || !input || !fixed_mask || !solution) return;

    // Build proposal with fixed cells enforced
    int8_t proposal[TRM_DECODED_CELL_COUNT];
    memcpy(proposal, decoded, sizeof(proposal));
    for (int i = 0; i < TRM_DECODED_CELL_COUNT; i++) {
        if (fixed_mask[i] == 1) proposal[i] = input[i];
    }

    // Check guard
    int valid = trm_fixture_is_sudoku_valid(proposal);
    analysis->guard_admitted = valid;

    if (valid) {
        analysis->rejection_class = TRM_GUARD_ADMITTED;
        return;
    }

    // Analyze rejected proposal
    int correct = 0, wrong = 0, fixed_violations = 0, compatible = 0;

    for (int i = 0; i < TRM_DECODED_CELL_COUNT; i++) {
        if (fixed_mask[i] == 0 && decoded[i] != input[i]) {
            if (decoded[i] == solution[i]) {
                correct++;
                // Check if individually compatible
                int8_t test[TRM_FIXTURE_CELL_COUNT];
                memcpy(test, input, sizeof(test));
                test[i] = decoded[i];
                if (trm_fixture_is_sudoku_valid(test)) {
                    compatible++;
                    analysis->compatible_correct_positions[compatible - 1] = (int8_t)i;
                }
            } else if (decoded[i] != 0) {
                wrong++;
            }
        }
        if (fixed_mask[i] == 1 && decoded[i] != input[i]) {
            fixed_violations++;
        }
    }

    analysis->correct_in_rejected = correct;
    analysis->wrong_in_rejected = wrong;
    analysis->fixed_violations = fixed_violations;
    analysis->compatible_correct_subset_size = compatible;

    // Classify rejection
    if (correct == 0 && wrong == 0) {
        analysis->rejection_class = TRM_REJECTED_NO_EFFECTIVE_WRITABLE_CHANGE;
    } else if (correct > 0 && wrong > 0) {
        analysis->rejection_class = TRM_REJECTED_MIXED_CORRECT_AND_WRONG;
    } else if (correct > 0 && wrong == 0) {
        analysis->rejection_class = TRM_REJECTED_CORRECT_BUT_MUTUALLY_INCOMPATIBLE;
    } else if (wrong > 0 && correct == 0) {
        analysis->rejection_class = TRM_REJECTED_ALL_HARMFUL;
    } else if (fixed_violations > 0) {
        analysis->rejection_class = TRM_REJECTED_CORRECT_PLUS_FIXED_VIOLATIONS;
    } else {
        analysis->rejection_class = TRM_REJECTED_ALL_HARMFUL;
    }
}
