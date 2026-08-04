#ifndef ELPIS_SEMANTIC_TRM_DECODER_ANALYSIS_H
#define ELPIS_SEMANTIC_TRM_DECODER_ANALYSIS_H

#include <stdint.h>

/* Define local constants to avoid cross-header dependency cycle */
#ifndef TRM_DECODED_CELL_COUNT
#define TRM_DECODED_CELL_COUNT 81
#endif

#define TRM_DECODER_RESULT_MAX 32

typedef enum {
    TRM_DECODER_P8_ARGMAX_LOWEST_TIEBREAK = 0,
    TRM_DECODER_NATIVE_DOCUMENTED = 1,
    TRM_DECODER_CLASS_ZERO_INTERPRETATION = 2,
    TRM_DECODER_GIVEN_CELL_OUTPUT = 3,
    TRM_DECODER_FULL_BOARD_VS_WRITABLE = 4,
} trm_decoder_type_t;

typedef struct {
    trm_decoder_type_t decoder_type;
    int8_t decoded[TRM_DECODED_CELL_COUNT];
    int32_t correct_additions;
    int32_t wrong_additions;
    int32_t fixed_violations;
    int decoders_identical;
    int32_t class_zero_writable;
} trm_decoder_result_t;

trm_decoder_result_t trm_decoder_result_create(trm_decoder_type_t type);
void trm_decoder_compare(const trm_decoder_result_t *p8,
                          const trm_decoder_result_t *native,
                          int8_t *diff_count,
                          int32_t *diff_correct,
                          int32_t *diff_wrong);

#endif
