/* elpis_semantic/trm_abi.h — Frozen TRM ABI descriptor v1.
 *
 * Immutable ABI contract for the frozen TRM model interface. Defines
 * the exact structural input/output tensor contract. Contains no model
 * path, checkpoint, weight digest, device index, or Python dependency.
 *
 * Identity domain: "elpis.semantic.trm_abi.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_ABI_H
#define ELPIS_SEMANTIC_TRM_ABI_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* TRM output semantics                                                 */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum trm_output_semantics {
    TRM_OUTPUT_DIGIT_CLASS_SCORES    = 0u,
    TRM_OUTPUT_DIGIT_CLASS_PROBABILITIES = 1u,
    TRM_OUTPUT_DIGIT_CLASS_ONE_HOT   = 2u,
    TRM_OUTPUT_DIGIT_CLASS_INDICES   = 3u,
} trm_output_semantics;

/* ──────────────────────────────────────────────────────────────────── */
/* ABI flags                                                              */
/* ──────────────────────────────────────────────────────────────────── */

#define TRM_ABI_FLAG_NONE              0u
#define TRM_ABI_FLAG_INPUT_MASK        0x01u  /* ABI accepts input mask */
#define TRM_ABI_FLAG_OUTPUT_MASK       0x02u  /* ABI emits output mask */
#define TRM_ABI_FLAG_MASK              0x03u

/* ──────────────────────────────────────────────────────────────────── */
/* ABI descriptor                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_trm_abi_v1 {
    uint32_t                          abi_version;

    /* Contract digest of the frozen semantic contract */
    hacf_digest                       semantic_contract_digest;

    /* Input specification */
    uint32_t                          input_rank;
    uint32_t                          input_dimensions[4];
    uint32_t                          input_dtype;    /* 0=FLOAT32 */
    uint32_t                          input_byte_order; /* 0=LITTLE_ENDIAN */
    uint32_t                          input_layout;   /* 0=ROW_MAJOR_CONTIGUOUS */
    uint32_t                          input_mask_supported;

    /* Output specification */
    uint32_t                          output_rank;
    uint32_t                          output_dimensions[4];
    uint32_t                          output_dtype;
    uint32_t                          output_semantics; /* trm_output_semantics */
    uint32_t                          output_mask_supported;

    /* Logical dimensions */
    uint32_t                          batch_size;
    uint32_t                          cell_count;
    uint32_t                          digit_class_count;

    /* ABI-level flags */
    uint32_t                          abi_flags;

    /* ABI identity digest */
    hacf_digest                       abi_digest;

    uint8_t                           reserved[64];
} elpis_semantic_trm_abi_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                             */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize with P8 v1 defaults: [1,81,10] float32, row-major, contiguous. */
void elpis_trm_abi_init(elpis_semantic_trm_abi_v1 *abi);

/* Compute ABI identity. Domain: "elpis.semantic.trm_abi.v1" */
int elpis_trm_abi_identity(
    const elpis_semantic_trm_abi_v1 *abi, hacf_digest *out);

/* Validate: ABI version, shape [1,81,10], known dtype, known output_semantics,
 * reserved zeroed, no model path/checkpoint fields. */
int elpis_trm_abi_validate(
    const elpis_semantic_trm_abi_v1 *abi);

/* Check if output_semantics value is known. */
int elpis_trm_abi_output_semantics_known(uint32_t semantics);

/* Persistence */
int elpis_write_trm_abi(const char *path,
    const elpis_semantic_trm_abi_v1 *abi);
int elpis_read_trm_abi(const char *path, elpis_semantic_trm_abi_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
