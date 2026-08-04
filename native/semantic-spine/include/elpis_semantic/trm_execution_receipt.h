/* trm_execution_receipt.h — Immutable execution receipt v1.
 *
 * Identity domain: "elpis.semantic.trm_execution_receipt.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_EXECUTION_RECEIPT_H
#define ELPIS_SEMANTIC_TRM_EXECUTION_RECEIPT_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_EXECUTION_RECEIPT_VERSION 1u

/* Disposition codes */
typedef enum trm_execution_disposition {
    TRM_EXECUTION_COMPLETE = 0u,
    TRM_EXECUTION_BLOCKED_BY_REQUEST = 1u,
    TRM_EXECUTION_BLOCKED_BY_MODEL = 2u,
    TRM_EXECUTION_BLOCKED_BY_RUNTIME = 3u,
    TRM_EXECUTION_BLOCKED_BY_TIMEOUT = 4u,
    TRM_EXECUTION_BLOCKED_BY_OUTPUT = 5u,
    TRM_EXECUTION_BLOCKED_INTERNAL = 6u,
} trm_execution_disposition;

/* Candidate payload element count: [1,81,10] float32 */
#define TRM_EXEC_RECEIPT_ELEMENTS (1u * GRID81_CELL_COUNT * GRID81_DIGIT_CLASS_COUNT)

typedef struct elpis_semantic_trm_execution_receipt_v1 {
    uint32_t                          abi_version;

    /* Binding digests */
    hacf_digest                       execution_request_digest;
    hacf_digest                       model_manifest_digest;
    hacf_digest                       runtime_policy_digest;
    hacf_digest                       input_tensor_digest;

    /* Output digests */
    hacf_digest                       candidate_frame_digest;
    hacf_digest                       candidate_payload_digest;

    /* Output semantics */
    uint32_t                          model_output_semantics; /* trm_output_semantics */

    /* Invocation metadata */
    uint32_t                          model_invocation_count;
    uint32_t                          input_mutation_detected;
    uint32_t                          model_artifact_mutation_detected;
    uint32_t                          nonfinite_output_detected;

    /* Disposition */
    uint32_t                          execution_disposition;   /* trm_execution_disposition */

    /* Candidate payload: raw model output [1][81][10] float32 */
    float                             candidate_payload[TRM_EXEC_RECEIPT_ELEMENTS];

    /* Trace */
    hacf_digest                       execution_trace_digest;

    /* HACF */
    hacf_digest                       HACF_package_digest;

    /* Receipt identity */
    hacf_digest                       execution_receipt_digest;

    /* Reserved */
    uint8_t                           reserved[64];
} elpis_semantic_trm_execution_receipt_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_trm_execution_receipt_init(
    elpis_semantic_trm_execution_receipt_v1 *receipt);

/* Compute receipt identity. Domain: "elpis.semantic.trm_execution_receipt.v1" */
int elpis_trm_execution_receipt_identity(
    const elpis_semantic_trm_execution_receipt_v1 *receipt, hacf_digest *out);

/* Validate: disposition valid, invocation_count==1 for COMPLETE,
 * no mutation detected, no nonfinite output, reserved zeroed. */
int elpis_trm_execution_receipt_validate(
    const elpis_semantic_trm_execution_receipt_v1 *receipt);

/* Persistence */
int elpis_write_trm_execution_receipt(const char *path,
    const elpis_semantic_trm_execution_receipt_v1 *receipt);
int elpis_read_trm_execution_receipt(const char *path,
    elpis_semantic_trm_execution_receipt_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
