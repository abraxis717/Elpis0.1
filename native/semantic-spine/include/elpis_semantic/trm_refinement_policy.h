/* trm_refinement_policy.h — Immutable bounded refinement policy v1.
 *
 * Identity domain: "elpis.semantic.trm_refinement_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_REFINEMENT_POLICY_H
#define ELPIS_SEMANTIC_TRM_REFINEMENT_POLICY_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_REFINEMENT_POLICY_VERSION 1u

typedef enum trm_cycle_identity_policy {
    TRM_CYCLE_EXACT_GRID81_DIGIT_ARRAY_DIGEST = 0u,
} trm_cycle_identity_policy;

typedef enum trm_state_commit_policy {
    TRM_COMMIT_ONLY_GUARDED_SUDOKU_VALID = 0u,
} trm_state_commit_policy;

typedef enum trm_failure_state_policy {
    TRM_RETAIN_LAST_COMMITTED_STATE = 0u,
} trm_failure_state_policy;

typedef struct elpis_semantic_trm_refinement_policy_v1 {
    uint32_t                          abi_version;

    /* Identity bindings */
    hacf_digest                       model_manifest_digest;
    hacf_digest                       runtime_policy_digest;
    hacf_digest                       P8_adapter_policy_digest;

    /* Limits */
    uint32_t                          maximum_steps;

    /* Stop conditions */
    uint32_t                          stop_on_no_change;
    uint32_t                          stop_on_complete_board;
    uint32_t                          stop_on_cycle;
    uint32_t                          stop_on_guard_rejection;
    uint32_t                          stop_on_execution_failure;

    /* Policy enums */
    uint32_t                          cycle_identity_policy;   /* trm_cycle_identity_policy */
    uint32_t                          state_commit_policy;     /* trm_state_commit_policy */
    uint32_t                          failure_state_policy;    /* trm_failure_state_policy */

    /* Policy identity */
    hacf_digest                       refinement_policy_digest;

    /* Reserved */
    uint8_t                           reserved[64];
} elpis_semantic_trm_refinement_policy_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_trm_refinement_policy_init(
    elpis_semantic_trm_refinement_policy_v1 *policy);

/* Compute policy identity. Domain: "elpis.semantic.trm_refinement_policy.v1" */
int elpis_trm_refinement_policy_identity(
    const elpis_semantic_trm_refinement_policy_v1 *policy, hacf_digest *out);

/* Validate: maximum_steps in range, stop conditions valid, reserved zeroed. */
int elpis_trm_refinement_policy_validate(
    const elpis_semantic_trm_refinement_policy_v1 *policy);

/* Persistence */
int elpis_write_trm_refinement_policy(const char *path,
    const elpis_semantic_trm_refinement_policy_v1 *policy);
int elpis_read_trm_refinement_policy(const char *path,
    elpis_semantic_trm_refinement_policy_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
