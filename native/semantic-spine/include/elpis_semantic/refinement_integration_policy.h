/* elpis_semantic/refinement_integration_policy.h — Integration policy v1.
 *
 * Immutable policy governing canonical refinement integration. Binds backend,
 * adapter, P8/P9 guards, and execution limits.
 *
 * Identity domain: "elpis.semantic.refinement_integration_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINEMENT_INTEGRATION_POLICY_H
#define ELPIS_SEMANTIC_REFINEMENT_INTEGRATION_POLICY_H

#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINEMENT_INTEGRATION_POLICY_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Policy fields                                                            */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_refinement_integration_policy_v1 {
    uint32_t                              abi_version;

    /* Backend registry binding */
    hacf_digest                           backend_registry_digest;

    /* Active backend identity */
    hacf_digest                           active_backend_digest;

    /* Active adapter identity */
    hacf_digest                           active_adapter_digest;

    /* P8 bindings */
    hacf_digest                           P8_candidate_frame_schema_digest;
    hacf_digest                           P8_decoder_policy_digest;
    hacf_digest                           P8_mutability_policy_digest;

    /* P9 bindings */
    hacf_digest                           P9_state_guard_digest;
    hacf_digest                           P9_refinement_policy_digest;

    /* Execution limits */
    uint32_t                              maximum_steps;

    /* Failure policy: RETAIN_LAST_COMMITTED (0), ABORT_ALL (1) */
    uint32_t                              failure_policy;

    /* Timeout policy: seconds per integration transaction */
    uint32_t                              timeout_seconds;

    /* State commit policy: SUDOKU_VALID_ONLY (0) */
    uint32_t                              state_commit_policy;

    /* Sidecar isolation: always 1 (inaccessible) */
    uint8_t                               sidecar_isolation_enforced;

    /* Reference isolation: always 1 (inaccessible) */
    uint8_t                               reference_isolation_enforced;

    /* Policy identity digest */
    hacf_digest                           integration_policy_digest;

    uint8_t                               reserved[128];
} elpis_semantic_refinement_integration_policy_v1;

/* Initialize */
void elpis_refinement_integration_policy_init(
    elpis_semantic_refinement_integration_policy_v1 *policy);

/* Compute policy identity. Domain: "elpis.semantic.refinement_integration_policy.v1" */
int elpis_refinement_integration_policy_identity(
    const elpis_semantic_refinement_integration_policy_v1 *policy, hacf_digest *out);

/* Validate: ABI version, digests non-zero where required, sidecar/reference enforced. */
int elpis_refinement_integration_policy_validate(
    const elpis_semantic_refinement_integration_policy_v1 *policy);

/* Persistence */
int elpis_write_refinement_integration_policy(const char *path,
    const elpis_semantic_refinement_integration_policy_v1 *policy);
int elpis_read_refinement_integration_policy(const char *path,
    elpis_semantic_refinement_integration_policy_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
