#ifndef ELPIS_SEMANTIC_TRM_GUARD_GRANULARITY_ANALYSIS_H
#define ELPIS_SEMANTIC_TRM_GUARD_GRANULARITY_ANALYSIS_H

#include <stdint.h>

/* Define local constants to avoid cross-header dependency cycle */
#ifndef TRM_DECODED_CELL_COUNT
#define TRM_DECODED_CELL_COUNT 81
#endif

#define TRM_FIXTURE_CELL_COUNT 81
#define TRM_GUARD_ANALYSIS_MAX 32

typedef enum {
    TRM_REJECTED_ALL_HARMFUL = 0,
    TRM_REJECTED_MIXED_CORRECT_AND_WRONG = 1,
    TRM_REJECTED_CORRECT_BUT_MUTUALLY_INCOMPATIBLE = 2,
    TRM_REJECTED_CORRECT_PLUS_FIXED_VIOLATIONS = 3,
    TRM_REJECTED_NO_EFFECTIVE_WRITABLE_CHANGE = 4,
    TRM_GUARD_ADMITTED = 5,
} trm_rejection_class_t;

typedef struct {
    uint32_t fixture_ordinal;
    int guard_admitted;
    trm_rejection_class_t rejection_class;
    int32_t correct_in_rejected;
    int32_t wrong_in_rejected;
    int32_t fixed_violations;
    int32_t compatible_correct_subset_size;
    int8_t compatible_correct_positions[TRM_DECODED_CELL_COUNT];
} trm_guard_analysis_t;

trm_guard_analysis_t trm_guard_analysis_create(uint32_t ordinal);
void trm_guard_analyze_proposal(trm_guard_analysis_t *analysis,
                                  const int8_t decoded[TRM_DECODED_CELL_COUNT],
                                  const int8_t input[TRM_FIXTURE_CELL_COUNT],
                                  const int8_t fixed_mask[TRM_FIXTURE_CELL_COUNT],
                                  const int8_t solution[TRM_FIXTURE_CELL_COUNT]);

#endif
