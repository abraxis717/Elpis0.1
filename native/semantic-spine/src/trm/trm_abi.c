/* trm_abi.c — Frozen TRM ABI descriptor v1. */

#include "elpis_semantic/trm_abi.h"
#include "elpis_semantic/trm_persist.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_trm_abi_init(elpis_semantic_trm_abi_v1 *abi) {
    if (!abi) return;
    memset(abi, 0, sizeof(*abi));
    abi->abi_version = TRM_ABI_VERSION;
    abi->input_rank = 3;
    abi->input_dimensions[0] = 1;
    abi->input_dimensions[1] = GRID81_CELL_COUNT;
    abi->input_dimensions[2] = GRID81_DIGIT_CLASS_COUNT;
    abi->input_dimensions[3] = 0;
    abi->input_dtype = 0;  /* FLOAT32 */
    abi->input_byte_order = 0; /* LITTLE_ENDIAN */
    abi->input_layout = 0;  /* ROW_MAJOR_CONTIGUOUS */
    abi->input_mask_supported = 0;
    abi->output_rank = 3;
    abi->output_dimensions[0] = 1;
    abi->output_dimensions[1] = GRID81_CELL_COUNT;
    abi->output_dimensions[2] = GRID81_DIGIT_CLASS_COUNT;
    abi->output_dimensions[3] = 0;
    abi->output_dtype = 0;  /* FLOAT32 */
    abi->output_semantics = TRM_OUTPUT_DIGIT_CLASS_SCORES;
    abi->output_mask_supported = 0;
    abi->batch_size = 1;
    abi->cell_count = GRID81_CELL_COUNT;
    abi->digit_class_count = GRID81_DIGIT_CLASS_COUNT;
    abi->abi_flags = TRM_ABI_FLAG_NONE;
}

int elpis_trm_abi_identity(const elpis_semantic_trm_abi_v1 *abi, hacf_digest *out) {
    if (!abi || !out) return SEMANTIC_E_INVAL;
    return elpis_trm_digest_domain("elpis.semantic.trm_abi.v1",
        abi->abi_version, (const uint8_t *)abi, sizeof(*abi), out);
}

int elpis_trm_abi_validate(const elpis_semantic_trm_abi_v1 *abi) {
    if (!abi) return SEMANTIC_E_INVAL;
    if (abi->abi_version != TRM_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (abi->input_rank != 3) return SEMANTIC_E_INVAL;
    if (abi->input_dimensions[0] != 1) return SEMANTIC_E_INVAL;
    if (abi->input_dimensions[1] != GRID81_CELL_COUNT) return SEMANTIC_E_INVAL;
    if (abi->input_dimensions[2] != GRID81_DIGIT_CLASS_COUNT) return SEMANTIC_E_INVAL;
    if (abi->output_rank != 3) return SEMANTIC_E_INVAL;
    if (abi->output_dimensions[0] != 1) return SEMANTIC_E_INVAL;
    if (abi->output_dimensions[1] != GRID81_CELL_COUNT) return SEMANTIC_E_INVAL;
    if (abi->output_dimensions[2] != GRID81_DIGIT_CLASS_COUNT) return SEMANTIC_E_INVAL;
    if (!elpis_trm_abi_output_semantics_known(abi->output_semantics)) return SEMANTIC_E_INVAL;
    if (abi->abi_flags & ~TRM_ABI_FLAG_MASK) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(abi->reserved); i++) {
        if (abi->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_trm_abi_output_semantics_known(uint32_t semantics) {
    return (semantics <= (uint32_t)TRM_OUTPUT_DIGIT_CLASS_INDICES);
}

int elpis_write_trm_abi(const char *path, const elpis_semantic_trm_abi_v1 *abi) {
    if (!path || !abi) return SEMANTIC_E_INVAL;
    return elpis_trm_write_binary(path, (const uint8_t *)abi, (uint32_t)sizeof(*abi));
}

int elpis_read_trm_abi(const char *path, elpis_semantic_trm_abi_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    memset(out, 0, sizeof(*out));
    uint32_t actual = 0;
    int ret = elpis_trm_read_binary(path, (uint8_t *)out, (uint32_t)sizeof(*out), &actual);
    if (ret < 0) return SEMANTIC_E_IO;
    if (actual != (uint32_t)sizeof(*out)) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}
