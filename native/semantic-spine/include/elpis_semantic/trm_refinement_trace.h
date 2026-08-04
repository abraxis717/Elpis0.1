/* trm_refinement_trace.h — Complete refinement trace v1.
 *
 * Identity domain: "elpis.semantic.trm_refinement_trace.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_REFINEMENT_TRACE_H
#define ELPIS_SEMANTIC_TRM_REFINEMENT_TRACE_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_REFINEMENT_TRACE_VERSION 1u

#define TRM_MAX_REFINEMENT_STEPS   16u

typedef struct elpis_semantic_trm_refinement_trace_v1 {
    uint32_t                          abi_version;

    /* Identity bindings */
    hacf_digest                       root_P7_structural_packet_digest;
    hacf_digest                       root_P8_adapter_packet_digest;
    hacf_digest                       model_manifest_digest;
    hacf_digest                       runtime_policy_digest;
    hacf_digest                       refinement_policy_digest;

    /* Step digests (ordered) */
    uint32_t                          step_count;
    hacf_digest                       step_digests[TRM_MAX_REFINEMENT_STEPS];

    /* Committed state digests (ordered) */
    uint32_t                          committed_state_count;
    hacf_digest                       committed_state_digests[TRM_MAX_REFINEMENT_STEPS + 1];

    /* Initial and final state digests */
    hacf_digest                       initial_state_digest;
    hacf_digest                       final_committed_state_digest;

    /* Invocation counts */
    uint32_t                          model_invocation_count;
    uint32_t                          committed_change_step_count;
    uint32_t                          total_admitted_changed_cells;
    uint32_t                          total_fixed_violation_attempts;

    /* HACF */
    hacf_digest                       HACF_package_digest;

    /* Trace identity */
    hacf_digest                       trace_digest;

    /* Reserved */
    uint8_t                           reserved[64];
} elpis_semantic_trm_refinement_trace_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_trm_refinement_trace_init(
    elpis_semantic_trm_refinement_trace_v1 *trace);

/* Compute trace identity. Domain: "elpis.semantic.trm_refinement_trace.v1" */
int elpis_trm_refinement_trace_identity(
    const elpis_semantic_trm_refinement_trace_v1 *trace, hacf_digest *out);

/* Validate: step count valid, committed states ordered, reserved zeroed. */
int elpis_trm_refinement_trace_validate(
    const elpis_semantic_trm_refinement_trace_v1 *trace);

/* Persistence */
int elpis_write_trm_refinement_trace(const char *path,
    const elpis_semantic_trm_refinement_trace_v1 *trace);
int elpis_read_trm_refinement_trace(const char *path,
    elpis_semantic_trm_refinement_trace_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
