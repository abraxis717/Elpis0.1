/* trm_input_tensor.c — Canonical TRM input tensor v1. */

#include "elpis_semantic/trm_input_tensor.h"
#include "elpis_semantic/trm_persist.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_trm_input_tensor_init(elpis_semantic_trm_input_tensor_v1 *tensor) {
    if (!tensor) return;
    memset(tensor, 0, sizeof(*tensor));
    tensor->abi_version = TRM_INPUT_TENSOR_VERSION;
    tensor->rank = 3;
    tensor->dimensions[0] = TRM_INPUT_BATCH;
    tensor->dimensions[1] = TRM_INPUT_CELLS;
    tensor->dimensions[2] = TRM_INPUT_CLASSES;
    tensor->dimensions[3] = 0;
    tensor->dtype = 0;  /* FLOAT32 */
    tensor->byte_order = 0; /* LITTLE_ENDIAN */
    tensor->layout = 0;  /* ROW_MAJOR_CONTIGUOUS */
    tensor->element_count = TRM_INPUT_ELEMENTS;
    tensor->payload_byte_count = (uint32_t)(TRM_INPUT_ELEMENTS * sizeof(float));
}

int elpis_trm_input_tensor_construct(
    elpis_semantic_trm_input_tensor_v1 *tensor,
    const uint32_t digit_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT],
    const hacf_digest *TRM_abi_digest,
    const hacf_digest *P7_digit_class_tensor_digest)
{
    if (!tensor || !digit_classes || !TRM_abi_digest || !P7_digit_class_tensor_digest) {
        return SEMANTIC_E_INVAL;
    }

    elpis_trm_input_tensor_init(tensor);

    memcpy(&tensor->TRM_abi_digest, TRM_abi_digest, sizeof(hacf_digest));
    memcpy(&tensor->P7_digit_class_tensor_digest, P7_digit_class_tensor_digest, sizeof(hacf_digest));

    /* Construct tensor from P7 digit-class binary values */
    for (uint32_t cell = 0; cell < GRID81_CELL_COUNT; cell++) {
        for (uint32_t cls = 0; cls < GRID81_DIGIT_CLASS_COUNT; cls++) {
            tensor->tensor[(size_t)cell * GRID81_DIGIT_CLASS_COUNT + cls] =
                (float)(int)digit_classes[cell][cls];
        }
    }

    /* Compute payload digest over 3240 bytes (810 * sizeof(float)) */
    elpis_trm_digest_bytes((const uint8_t *)tensor->tensor,
        (size_t)tensor->payload_byte_count, &tensor->tensor_payload_digest);

    memset(tensor->reserved, 0, sizeof(tensor->reserved));
    return SEMANTIC_OK;
}

int elpis_trm_input_tensor_identity(const elpis_semantic_trm_input_tensor_v1 *tensor, hacf_digest *out) {
    if (!tensor || !out) return SEMANTIC_E_INVAL;
    return elpis_trm_digest_domain("elpis.semantic.trm_input_tensor.v1",
        tensor->abi_version, (const uint8_t *)tensor, sizeof(*tensor), out);
}

int elpis_trm_input_tensor_validate(
    const elpis_semantic_trm_input_tensor_v1 *tensor,
    const uint32_t P7_digits[GRID81_CELL_COUNT])
{
    if (!tensor) return SEMANTIC_E_INVAL;
    if (tensor->abi_version != TRM_INPUT_TENSOR_VERSION) return SEMANTIC_E_INVAL;
    if (tensor->rank != 3) return SEMANTIC_E_INVAL;
    if (tensor->dimensions[0] != TRM_INPUT_BATCH) return SEMANTIC_E_INVAL;
    if (tensor->dimensions[1] != TRM_INPUT_CELLS) return SEMANTIC_E_INVAL;
    if (tensor->dimensions[2] != TRM_INPUT_CLASSES) return SEMANTIC_E_INVAL;

    /* Each value must be exactly 0.0f or 1.0f */
    for (uint32_t i = 0; i < TRM_INPUT_ELEMENTS; i++) {
        if (tensor->tensor[i] != 0.0f && tensor->tensor[i] != 1.0f) {
            return SEMANTIC_E_INVAL;
        }
    }

    /* If P7 digits provided, verify argmax reproduces them */
    if (P7_digits) {
        for (uint32_t cell = 0; cell < GRID81_CELL_COUNT; cell++) {
            uint32_t argmax_class = 0;
            for (uint32_t cls = 0; cls < GRID81_DIGIT_CLASS_COUNT; cls++) {
                if (tensor->tensor[(size_t)cell * GRID81_DIGIT_CLASS_COUNT + cls] == 1.0f) {
                    argmax_class = cls;
                    break;
                }
            }
            if (argmax_class != P7_digits[cell]) return SEMANTIC_E_INVAL;
        }
    }

    for (size_t i = 0; i < sizeof(tensor->reserved); i++) {
        if (tensor->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_trm_input_tensor(const char *path, const elpis_semantic_trm_input_tensor_v1 *tensor) {
    if (!path || !tensor) return SEMANTIC_E_INVAL;
    return elpis_trm_write_binary(path, (const uint8_t *)tensor, (uint32_t)sizeof(*tensor));
}

int elpis_read_trm_input_tensor(const char *path, elpis_semantic_trm_input_tensor_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    memset(out, 0, sizeof(*out));
    uint32_t actual = 0;
    int ret = elpis_trm_read_binary(path, (uint8_t *)out, (uint32_t)sizeof(*out), &actual);
    if (ret < 0) return SEMANTIC_E_IO;
    if (actual != (uint32_t)sizeof(*out)) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}
