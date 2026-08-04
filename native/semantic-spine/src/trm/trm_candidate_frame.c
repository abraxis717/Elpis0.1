/* trm_candidate_frame.c — TRM candidate-output frame ABI v1. */

#include "elpis_semantic/trm_candidate_frame.h"
#include "elpis_semantic/trm_persist.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <math.h>
#include <string.h>
#include <stdint.h>

void elpis_trm_candidate_frame_init(elpis_semantic_trm_candidate_frame_v1 *frame) {
    if (!frame) return;
    memset(frame, 0, sizeof(*frame));
    frame->abi_version = TRM_CANDIDATE_FRAME_VERSION;
    frame->rank = 3;
    frame->dimensions[0] = 1;
    frame->dimensions[1] = GRID81_CELL_COUNT;
    frame->dimensions[2] = GRID81_DIGIT_CLASS_COUNT;
    frame->dimensions[3] = 0;
    frame->dtype = 0;  /* FLOAT32 */
    frame->byte_order = 0; /* LITTLE_ENDIAN */
    frame->layout = 0;  /* ROW_MAJOR_CONTIGUOUS */
    frame->element_count = TRM_CANDIDATE_ELEMENTS;
    frame->payload_byte_count = (uint32_t)(TRM_CANDIDATE_ELEMENTS * sizeof(float));
}

int elpis_trm_candidate_frame_identity(
    const elpis_semantic_trm_candidate_frame_v1 *frame, hacf_digest *out)
{
    if (!frame || !out) return SEMANTIC_E_INVAL;
    return elpis_trm_digest_domain("elpis.semantic.trm_candidate_frame.v1",
        frame->abi_version, (const uint8_t *)frame, sizeof(*frame), out);
}

int elpis_trm_candidate_frame_validate(const elpis_semantic_trm_candidate_frame_v1 *frame) {
    if (!frame) return SEMANTIC_E_INVAL;
    if (frame->abi_version != TRM_CANDIDATE_FRAME_VERSION) return SEMANTIC_E_INVAL;

    /* Candidate kind must be known */
    if (frame->candidate_kind > (uint32_t)TRM_OUTPUT_DIGIT_CLASS_INDICES) {
        return SEMANTIC_E_INVAL;
    }

    /* Validate dimensions based on kind */
    if (frame->candidate_kind == (uint32_t)TRM_OUTPUT_DIGIT_CLASS_INDICES) {
        /* [1,81] indices */
        if (frame->rank != 2) return SEMANTIC_E_INVAL;
        if (frame->dimensions[0] != 1) return SEMANTIC_E_INVAL;
        if (frame->dimensions[1] != GRID81_CELL_COUNT) return SEMANTIC_E_INVAL;
    } else {
        /* [1,81,10] scores/probs/one-hot */
        if (frame->rank != 3) return SEMANTIC_E_INVAL;
        if (frame->dimensions[0] != 1) return SEMANTIC_E_INVAL;
        if (frame->dimensions[1] != GRID81_CELL_COUNT) return SEMANTIC_E_INVAL;
        if (frame->dimensions[2] != GRID81_DIGIT_CLASS_COUNT) return SEMANTIC_E_INVAL;

        /* Check for NaN or Inf */
        for (uint32_t i = 0; i < TRM_CANDIDATE_ELEMENTS; i++) {
            if (isnan(frame->candidate[i]) || isinf(frame->candidate[i])) {
                return SEMANTIC_E_INVAL;
            }
        }

        /* For one-hot: each cell must have exactly one 1.0f and rest 0.0f */
        if (frame->candidate_kind == (uint32_t)TRM_OUTPUT_DIGIT_CLASS_ONE_HOT) {
            for (uint32_t cell = 0; cell < GRID81_CELL_COUNT; cell++) {
                uint32_t ones = 0;
                for (uint32_t cls = 0; cls < GRID81_DIGIT_CLASS_COUNT; cls++) {
                    float v = frame->candidate[(size_t)cell * GRID81_DIGIT_CLASS_COUNT + cls];
                    if (v != 0.0f && v != 1.0f) return SEMANTIC_E_INVAL;
                    if (v == 1.0f) ones++;
                }
                if (ones != 1) return SEMANTIC_E_INVAL;
            }
        }
    }

    /* For indices: each value in 0-9 */
    if (frame->candidate_kind == (uint32_t)TRM_OUTPUT_DIGIT_CLASS_INDICES) {
        for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
            int val = (int)frame->candidate[i];
            if (val < 0 || val > 9) return SEMANTIC_E_INVAL;
        }
    }

    /* Source adapter packet must be non-zero */
    for (uint32_t i = 0; i < HACF_DIGEST_BYTES; i++) {
        if (frame->source_adapter_packet_digest.bytes[i] != 0) break;
        if (i == HACF_DIGEST_BYTES - 1) return SEMANTIC_E_INVAL;
    }

    for (size_t i = 0; i < sizeof(frame->reserved); i++) {
        if (frame->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_trm_candidate_frame(const char *path, const elpis_semantic_trm_candidate_frame_v1 *frame) {
    if (!path || !frame) return SEMANTIC_E_INVAL;
    return elpis_trm_write_binary(path, (const uint8_t *)frame, (uint32_t)sizeof(*frame));
}

int elpis_read_trm_candidate_frame(const char *path, elpis_semantic_trm_candidate_frame_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    memset(out, 0, sizeof(*out));
    uint32_t actual = 0;
    int ret = elpis_trm_read_binary(path, (uint8_t *)out, (uint32_t)sizeof(*out), &actual);
    if (ret < 0) return SEMANTIC_E_IO;
    if (actual != (uint32_t)sizeof(*out)) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}
