/* elpis_semantic/structural_spine_request.h — Integrated structural spine request v1.
 *
 * Carries all bound manifests needed to execute the P5→P12 spine path.
 * Contains NO model-server endpoint, GPU index, benchmark reference solution,
 * projector weights, residual81, or host-direction vector.
 *
 * Identity domain: "elpis.semantic.structural_spine_request.v1"
 */
#ifndef ELPIS_SEMANTIC_STRUCTURAL_SPINE_REQUEST_H
#define ELPIS_SEMANTIC_STRUCTURAL_SPINE_REQUEST_H

#include "elpis_semantic/structural_spine_policy.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SPINE_REQUEST_ABI_VERSION 1u

/* Maximum ordered digests for committed states */
#define SPINE_MAX_COMMITTED_DIGESTS 32u

typedef struct elpis_semantic_structural_spine_request_v1 {
    uint32_t                          abi_version;

    /* Bound policy */
    elpis_semantic_structural_spine_policy_v1 bound_policy;

    /* Bound phase inputs */
    hacf_digest                       P5_bounded_view_handoff_digest;
    hacf_digest                       P6_compiler_policy_digest;
    hacf_digest                       P7_compiler_policy_digest;
    hacf_digest                       P8_adapter_policy_digest;
    hacf_digest                       P8_guard_policy_digest;
    hacf_digest                       P12_backend_registry_digest;
    hacf_digest                       P12_integration_policy_digest;

    /* Active backend */
    char                              active_backend[SPINE_MAX_BACKEND_NAME];

    /* Execution boundary */
    uint32_t                          maximum_step_boundary;

    /* Request identity */
    hacf_digest                       request_digest;
    hacf_digest                       HACF_package_digest;

    uint8_t                           reserved[128];
} elpis_semantic_structural_spine_request_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_spine_request_init(
    elpis_semantic_structural_spine_request_v1 *request,
    const elpis_semantic_structural_spine_policy_v1 *policy);
int elpis_spine_request_identity(
    const elpis_semantic_structural_spine_request_v1 *req, hacf_digest *out);
int elpis_spine_request_validate(
    const elpis_semantic_structural_spine_request_v1 *req);
int elpis_spine_request_is_clean(
    const elpis_semantic_structural_spine_request_v1 *req);

#ifdef __cplusplus
}
#endif

#endif /* ELPIS_SEMANTIC_STRUCTURAL_SPINE_REQUEST_H */
