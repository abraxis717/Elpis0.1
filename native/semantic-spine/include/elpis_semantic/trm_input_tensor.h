/* elpis_semantic/trm_input_tensor.h — Canonical TRM input tensor v1.
 *
 * Constructs the exact [1,81,10] float32 tensor from P7 digit-class values.
 * Values are exactly 0.0f or 1.0f. No normalization, scaling, or embedding.
 *
 * Identity domain: "elpis.semantic.trm_input_tensor.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_INPUT_TENSOR_H
#define ELPIS_SEMANTIC_TRM_INPUT_TENSOR_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_INPUT_TENSOR_VERSION 1u

/* Tensor dimensions */
#define TRM_INPUT_BATCH       1u
#define TRM_INPUT_CELLS       GRID81_CELL_COUNT
#define TRM_INPUT_CLASSES     GRID81_DIGIT_CLASS_COUNT
#define TRM_INPUT_ELEMENTS    (TRM_INPUT_BATCH * TRM_INPUT_CELLS * TRM_INPUT_CLASSES)

/* ──────────────────────────────────────────────────────────────────── */
/* Input tensor record                                                    */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_trm_input_tensor_v1 {
    uint32_t                          abi_version;

    /* ABI binding */
    hacf_digest                       TRM_abi_digest;
    hacf_digest                       P7_digit_class_tensor_digest;

    /* Shape and layout */
    uint32_t                          rank;
    uint32_t                          dimensions[4];
    uint32_t                          dtype;    /* 0=FLOAT32 */
    uint32_t                          byte_order; /* 0=LITTLE_ENDIAN */
    uint32_t                          layout;   /* 0=ROW_MAJOR_CONTIGUOUS */

    /* Size */
    uint32_t                          element_count;
    uint32_t                          payload_byte_count;

    /* Payload: [1][81][10] float32, row-major, cell-major, class-last */
    float                             tensor[TRM_INPUT_ELEMENTS];

    /* Payload digest */
    hacf_digest                       tensor_payload_digest;

    /* Identity digest */
    hacf_digest                       tensor_identity_digest;

    uint8_t                           reserved[64];
} elpis_semantic_trm_input_tensor_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                             */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize: set ABI version, shape, dtype, zero tensor and reserved. */
void elpis_trm_input_tensor_init(
    elpis_semantic_trm_input_tensor_v1 *tensor);

/* Construct from P7 digit-class binary values.
 * digit_classes[cell][class] == 1 -> 1.0f, else 0.0f */
int elpis_trm_input_tensor_construct(
    elpis_semantic_trm_input_tensor_v1 *tensor,
    const uint32_t digit_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT],
    const hacf_digest *TRM_abi_digest,
    const hacf_digest *P7_digit_class_tensor_digest);

/* Compute tensor identity. Domain: "elpis.semantic.trm_input_tensor.v1" */
int elpis_trm_input_tensor_identity(
    const elpis_semantic_trm_input_tensor_v1 *tensor, hacf_digest *out);

/* Validate: shape, dtype, exactly 0.0 or 1.0 values, argmax reproduces P7 digits. */
int elpis_trm_input_tensor_validate(
    const elpis_semantic_trm_input_tensor_v1 *tensor,
    const uint32_t P7_digits[GRID81_CELL_COUNT]);

/* Persistence */
int elpis_write_trm_input_tensor(const char *path,
    const elpis_semantic_trm_input_tensor_v1 *tensor);
int elpis_read_trm_input_tensor(const char *path,
    elpis_semantic_trm_input_tensor_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
