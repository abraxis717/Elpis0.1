#include "elpis_semantic/trm_decoder_analysis.h"
#include <string.h>

trm_decoder_result_t trm_decoder_result_create(trm_decoder_type_t type) {
    trm_decoder_result_t result;
    memset(&result, 0, sizeof(result));
    result.decoder_type = type;
    return result;
}

void trm_decoder_compare(const trm_decoder_result_t *p8,
                          const trm_decoder_result_t *native,
                          int8_t *diff_count,
                          int32_t *diff_correct,
                          int32_t *diff_wrong) {
    if (!p8 || !native) return;

    int diffs = 0;
    for (int i = 0; i < TRM_DECODED_CELL_COUNT; i++) {
        if (p8->decoded[i] != native->decoded[i]) diffs++;
    }
    if (diff_count) *diff_count = (int8_t)diffs;
    if (diff_correct) *diff_correct = native->correct_additions - p8->correct_additions;
    if (diff_wrong) *diff_wrong = native->wrong_additions - p8->wrong_additions;
}
