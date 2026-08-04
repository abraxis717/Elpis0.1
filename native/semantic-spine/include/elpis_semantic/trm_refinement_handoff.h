/* trm_refinement_handoff.h — Downstream handoff v1.
 *
 * Identity domain: "elpis.semantic.trm_refinement_handoff.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_REFINEMENT_HANDOFF_H
#define ELPIS_SEMANTIC_TRM_REFINEMENT_HANDOFF_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_REFINEMENT_HANDOFF_VERSION 1u

typedef enum trm_handoff_kind {
    TRM_HANDOFF_FROZEN_TRM_REFINEMENT_RESULT = 0u,
} trm_handoff_kind;

typedef struct elpis_semantic_trm_refinement_handoff_v1 {
    uint32_t                          abi_version;

    /* Handoff kind */
    uint32_t                          handoff_kind;    /* trm_handoff_kind */

    /* Identity bindings */
    hacf_digest                       root_query_overlay_digest;
    hacf_digest                       P7_structural_packet_digest;
    hacf_digest                       P8_adapter_packet_digest;
    hacf_digest                       model_manifest_digest;
    hacf_digest                       runtime_policy_digest;
    hacf_digest                       refinement_policy_digest;
    hacf_digest                       refinement_trace_digest;
    hacf_digest                       refinement_result_digest;

    /* Final state */
    hacf_digest                       final_state_digest;

    /* Static masks */
    hacf_digest                       static_fixed_mask_digest;
    hacf_digest                       static_writable_mask_digest;

    /* Semantic trace sidecar (external — never entered model) */
    hacf_digest                       semantic_trace_sidecar_digest;

    /* Handoff policy */
    hacf_digest                       handoff_policy_digest;

    /* HACF */
    hacf_digest                       HACF_package_digest;

    /* Handoff identity */
    hacf_digest                       handoff_digest;

    /* Reserved */
    uint8_t                           reserved[64];
} elpis_semantic_trm_refinement_handoff_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_trm_refinement_handoff_init(
    elpis_semantic_trm_refinement_handoff_v1 *handoff);

/* Compute handoff identity. Domain: "elpis.semantic.trm_refinement_handoff.v1" */
int elpis_trm_refinement_handoff_identity(
    const elpis_semantic_trm_refinement_handoff_v1 *handoff, hacf_digest *out);

/* Validate: kind valid, all digests present, reserved zeroed. */
int elpis_trm_refinement_handoff_validate(
    const elpis_semantic_trm_refinement_handoff_v1 *handoff);

/* Persistence */
int elpis_write_trm_refinement_handoff(const char *path,
    const elpis_semantic_trm_refinement_handoff_v1 *handoff);
int elpis_read_trm_refinement_handoff(const char *path,
    elpis_semantic_trm_refinement_handoff_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
