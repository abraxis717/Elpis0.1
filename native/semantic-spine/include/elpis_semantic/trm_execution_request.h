/* trm_execution_request.h — Numeric-only execution request v1.
 *
 * Identity domain: "elpis.semantic.trm_execution_request.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_EXECUTION_REQUEST_H
#define ELPIS_SEMANTIC_TRM_EXECUTION_REQUEST_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_EXECUTION_REQUEST_VERSION 1u

/* Input tensor element count: [1,81,10] float32 */
#define TRM_EXEC_REQUEST_ELEMENTS (1u * GRID81_CELL_COUNT * GRID81_DIGIT_CLASS_COUNT)

typedef struct elpis_semantic_trm_execution_request_v1 {
    uint32_t                          abi_version;

    /* Binding digests */
    hacf_digest                       P8_execution_handoff_digest;
    hacf_digest                       P8_adapter_packet_digest;
    hacf_digest                       model_manifest_digest;
    hacf_digest                       runtime_policy_digest;
    hacf_digest                       TRM_abi_digest;

    /* Input tensor */
    hacf_digest                       input_tensor_digest;
    hacf_digest                       input_tensor_payload_digest;

    /* Refinement context */
    hacf_digest                       refinement_state_digest_or_zero;
    uint32_t                          step_index;

    /* Input tensor payload: [1][81][10] float32, row-major */
    float                             input_tensor[TRM_EXEC_REQUEST_ELEMENTS];

    /* HACF */
    hacf_digest                       HACF_package_digest;

    /* Request identity */
    hacf_digest                       execution_request_digest;

    /* Reserved */
    uint8_t                           reserved[64];
} elpis_semantic_trm_execution_request_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_trm_execution_request_init(
    elpis_semantic_trm_execution_request_v1 *request);

/* Compute request identity. Domain: "elpis.semantic.trm_execution_request.v1" */
int elpis_trm_execution_request_identity(
    const elpis_semantic_trm_execution_request_v1 *request, hacf_digest *out);

/* Validate: digests present, step_index valid, tensor has no NaN/Inf,
 * reserved zeroed. No semantic sidecar bytes present. */
int elpis_trm_execution_request_validate(
    const elpis_semantic_trm_execution_request_v1 *request);

/* Persistence */
int elpis_write_trm_execution_request(const char *path,
    const elpis_semantic_trm_execution_request_v1 *request);
int elpis_read_trm_execution_request(const char *path,
    elpis_semantic_trm_execution_request_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
