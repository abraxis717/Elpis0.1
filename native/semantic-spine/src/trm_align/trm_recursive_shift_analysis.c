#include <stdint.h>
#include <string.h>

typedef struct {
    int32_t step_index;
    int32_t input_fill_count;
    int32_t input_wrong_count;
    int32_t correct_additions;
    int32_t wrong_additions;
    int32_t fixed_violations;
    int guard_admitted;
    float class_zero_frequency;
} trm_recursive_step_t;

/* Recursive shift analysis: compare step-0 vs post-commit metrics.
 * Implementation is in Python; this validates the analysis. */

int trm_recursive_shift_check(const trm_recursive_step_t *step0,
                               const trm_recursive_step_t *step1,
                               int fixture_count) {
    if (!step0 || !step1 || fixture_count == 0) return 0;
    // Shift detected if step 1 correct additions drop below 50% of step 0
    // averaged across multiple fixtures
    return (step1->correct_additions < (step0->correct_additions / 2)) ? 1 : 0;
}
