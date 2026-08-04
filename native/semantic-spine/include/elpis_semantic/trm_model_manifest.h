/* trm_model_manifest.h — Immutable frozen-model manifest v1.
 *
 * Binds the exact frozen TRM model identity by digest.
 * Identity domain: "elpis.semantic.trm_model_manifest.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_MODEL_MANIFEST_H
#define ELPIS_SEMANTIC_TRM_MODEL_MANIFEST_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_MODEL_MANIFEST_VERSION 1u

#define TRM_MANIFEST_NAME_MAX      64u
#define TRM_MANIFEST_DIGEST_COUNT  8u

typedef struct elpis_semantic_trm_model_manifest_v1 {
    uint32_t                          abi_version;

    /* Architecture identity */
    char                              architecture_name[TRM_MANIFEST_NAME_MAX];
    char                              architecture_version[TRM_MANIFEST_NAME_MAX];

    /* ABI digest */
    hacf_digest                       TRM_abi_digest;

    /* Architecture source digests (ordered) */
    uint32_t                          architecture_source_count;
    hacf_digest                       architecture_source_digests[TRM_MANIFEST_DIGEST_COUNT];

    /* Configuration digests (ordered) */
    uint32_t                          configuration_count;
    hacf_digest                       configuration_digests[TRM_MANIFEST_DIGEST_COUNT];

    /* Weight file digests (ordered) */
    uint32_t                          weight_file_count;
    hacf_digest                       weight_file_digests[TRM_MANIFEST_DIGEST_COUNT];

    /* Weight metadata */
    char                              weight_format[TRM_MANIFEST_NAME_MAX];
    int64_t                           parameter_count;
    int64_t                           frozen_parameter_count;
    int64_t                           trainable_parameter_count;

    /* Expected I/O ABI */
    uint32_t                          expected_input_rank;
    uint32_t                          expected_input_dimensions[4];
    uint32_t                          expected_input_dtype;      /* 0=FLOAT32 */
    uint32_t                          expected_output_rank;
    uint32_t                          expected_output_dimensions[4];
    uint32_t                          expected_output_dtype;     /* 0=FLOAT32 */
    uint32_t                          expected_output_semantics; /* trm_output_semantics */

    /* Execution requirements */
    uint8_t                           model_eval_required;       /* 1=TRUE */
    uint8_t                           gradient_disable_required; /* 1=TRUE */
    uint8_t                           CPU_execution_supported;   /* 1=TRUE */

    /* Manifest identity */
    hacf_digest                       model_manifest_digest;

    /* Reserved */
    uint8_t                           reserved[128];
} elpis_semantic_trm_model_manifest_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_trm_model_manifest_init(
    elpis_semantic_trm_model_manifest_v1 *manifest);

/* Compute manifest identity. Domain: "elpis.semantic.trm_model_manifest.v1" */
int elpis_trm_model_manifest_identity(
    const elpis_semantic_trm_model_manifest_v1 *manifest, hacf_digest *out);

/* Validate: frozen_parameter_count == parameter_count,
 * model_eval_required, gradient_disable_required, CPU_execution_supported,
 * input/output shape matches P8 ABI, reserved zeroed. */
int elpis_trm_model_manifest_validate(
    const elpis_semantic_trm_model_manifest_v1 *manifest);

/* Persistence */
int elpis_write_trm_model_manifest(const char *path,
    const elpis_semantic_trm_model_manifest_v1 *manifest);
int elpis_read_trm_model_manifest(const char *path,
    elpis_semantic_trm_model_manifest_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
