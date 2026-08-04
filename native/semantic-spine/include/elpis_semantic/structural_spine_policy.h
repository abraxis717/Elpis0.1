/* elpis_semantic/structural_spine_policy.h — Immutable structural spine policy v1.
 *
 * Binds every qualified boundary from P5 through P12 into one immutable
 * closure policy. DETERMINISTIC_MRV_SOLVER is the sole active backend.
 * No caller-controlled backend selection. No runtime admission.
 *
 * Identity domain: "elpis.semantic.structural_spine_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_STRUCTURAL_SPINE_POLICY_H
#define ELPIS_SEMANTIC_STRUCTURAL_SPINE_POLICY_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SPINE_POLICY_ABI_VERSION 1u
#define SPINE_MAX_BACKEND_NAME 64u
#define SPINE_MAX_POLICY_ENUM  16u

/* ──────────────────────────────────────────────────────────────────── */
/* Policy enumerations                                                  */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum spine_semantic_mutation_policy {
    SPINE_SEMANTIC_MUTATION_FORBIDDEN = 0,
} spine_semantic_mutation_policy;

typedef enum spine_authority_mutation_policy {
    SPINE_AUTHORITY_MUTATION_FORBIDDEN = 0,
} spine_authority_mutation_policy;

typedef enum spine_sidecar_access_policy {
    SPINE_SIDECAR_ACCESS_FORBIDDEN = 0,
} spine_sidecar_access_policy;

typedef enum spine_reference_access_policy {
    SPINE_REFERENCE_ACCESS_FORBIDDEN = 0,
} spine_reference_access_policy;

typedef enum spine_state_commit_policy {
    SPINE_STATE_COMMIT_GUARDED_SUDOKU_VALID_ONLY = 0,
} spine_state_commit_policy;

typedef enum spine_failure_policy {
    SPINE_FAILURE_RETAIN_LAST_COMMITTED_STATE = 0,
} spine_failure_policy;

typedef enum spine_closure_policy {
    SPINE_CLOSURE_EXACT_BOUNDARY_REPLAY_REQUIRED = 0,
} spine_closure_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* Policy record                                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_structural_spine_policy_v1 {
    uint32_t                          abi_version;

    /* Bound phase digests */
    hacf_digest                       P5_handoff_digest;
    hacf_digest                       P6_topology_policy_digest;
    hacf_digest                       P7_grid81_policy_digest;
    hacf_digest                       P8_adapter_policy_digest;
    hacf_digest                       P9_guard_policy_digest;
    hacf_digest                       P12_integration_policy_digest;

    /* Active backend identity (string + digest) */
    char                              active_backend[SPINE_MAX_BACKEND_NAME];
    char                              active_adapter[SPINE_MAX_BACKEND_NAME];
    hacf_digest                       active_backend_digest;
    hacf_digest                       active_adapter_digest;

    /* Refinement boundary */
    uint32_t                          maximum_refinement_steps;

    /* Policy enforcement */
    uint32_t                          semantic_mutation_policy;
    uint32_t                          authority_mutation_policy;
    uint32_t                          sidecar_access_policy;
    uint32_t                          reference_access_policy;
    uint32_t                          state_commit_policy;
    uint32_t                          failure_policy;
    uint32_t                          closure_policy;

    /* Policy identity */
    hacf_digest                       spine_policy_digest;

    uint8_t                           reserved[128];
} elpis_semantic_structural_spine_policy_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_spine_policy_init(elpis_semantic_structural_spine_policy_v1 *policy);
int elpis_spine_policy_identity(
    const elpis_semantic_structural_spine_policy_v1 *policy, hacf_digest *out);
int elpis_spine_policy_validate(const elpis_semantic_structural_spine_policy_v1 *policy);
int elpis_spine_policy_is_canonical_backend(
    const elpis_semantic_structural_spine_policy_v1 *policy);
int elpis_spine_policy_is_ACTV1_blocked(
    const elpis_semantic_structural_spine_policy_v1 *policy);

#ifdef __cplusplus
}
#endif

#endif /* ELPIS_SEMANTIC_STRUCTURAL_SPINE_POLICY_H */
