/* trm_runtime_policy.h — Immutable CPU execution policy v1.
 *
 * Identity domain: "elpis.semantic.trm_runtime_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_RUNTIME_POLICY_H
#define ELPIS_SEMANTIC_TRM_RUNTIME_POLICY_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_RUNTIME_POLICY_VERSION 1u

/* Policy enums */
typedef enum trm_device_policy {
    TRM_DEVICE_CPU_ONLY = 0u,
} trm_device_policy;

typedef enum trm_evaluation_mode_policy {
    TRM_EVAL_REQUIRED = 0u,
} trm_evaluation_mode_policy;

typedef enum trm_gradient_policy {
    TRM_GRADIENT_DISABLED = 0u,
} trm_gradient_policy;

typedef enum trm_sampling_policy {
    TRM_SAMPLING_DISABLED = 0u,
} trm_sampling_policy;

typedef enum trm_randomness_policy {
    TRM_RANDOMNESS_FORBIDDEN = 0u,
} trm_randomness_policy;

typedef enum trm_input_mutation_policy {
    TRM_INPUT_MUTATION_FORBIDDEN = 0u,
} trm_input_mutation_policy;

typedef enum trm_output_capture_policy {
    TRM_OUTPUT_CAPTURE_EXACT = 0u,
} trm_output_capture_policy;

typedef enum trm_failure_policy {
    TRM_FAILURE_FAIL_CLOSED = 0u,
} trm_failure_policy;

typedef struct elpis_semantic_trm_runtime_policy_v1 {
    uint32_t                          abi_version;

    /* Identity bindings */
    hacf_digest                       model_manifest_digest;
    hacf_digest                       TRM_abi_digest;

    /* Policies */
    uint32_t                          device_policy;             /* trm_device_policy */
    uint32_t                          evaluation_mode_policy;    /* trm_evaluation_mode_policy */
    uint32_t                          gradient_policy;           /* trm_gradient_policy */
    uint32_t                          sampling_policy;           /* trm_sampling_policy */
    uint32_t                          thread_policy;             /* 0=SINGLE_THREAD */
    uint32_t                          randomness_policy;         /* trm_randomness_policy */
    uint32_t                          input_mutation_policy;     /* trm_input_mutation_policy */
    uint32_t                          output_capture_policy;     /* trm_output_capture_policy */
    uint32_t                          timeout_policy;            /* trm_failure_policy */
    uint32_t                          failure_policy;            /* trm_failure_policy */

    /* Thread counts */
    uint32_t                          CPU_intraop_thread_count;
    uint32_t                          CPU_interop_thread_count;

    /* Timeout */
    uint32_t                          maximum_step_wall_seconds;

    /* Policy identity */
    hacf_digest                       runtime_policy_digest;

    /* Reserved */
    uint8_t                           reserved[64];
} elpis_semantic_trm_runtime_policy_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_trm_runtime_policy_init(
    elpis_semantic_trm_runtime_policy_v1 *policy);

/* Compute policy identity. Domain: "elpis.semantic.trm_runtime_policy.v1" */
int elpis_trm_runtime_policy_identity(
    const elpis_semantic_trm_runtime_policy_v1 *policy, hacf_digest *out);

/* Validate: CPU only, eval required, gradients disabled,
 * sampling disabled, randomness forbidden, input mutation forbidden,
 * single thread, timeout > 0, reserved zeroed. */
int elpis_trm_runtime_policy_validate(
    const elpis_semantic_trm_runtime_policy_v1 *policy);

/* Persistence */
int elpis_write_trm_runtime_policy(const char *path,
    const elpis_semantic_trm_runtime_policy_v1 *policy);
int elpis_read_trm_runtime_policy(const char *path,
    elpis_semantic_trm_runtime_policy_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
