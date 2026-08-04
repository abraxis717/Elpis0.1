/* elpis_semantic/trm_execution_handoff.h — Future TRM execution handoff v1.
 *
 * Declares the sealed boundary for P9 frozen TRM execution. Binds the
 * P8 adapter packet and explicitly declares what P9 may and may not do.
 *
 * Identity domain: "elpis.semantic.trm_execution_handoff.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_EXECUTION_HANDOFF_H
#define ELPIS_SEMANTIC_TRM_EXECUTION_HANDOFF_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_EXECUTION_HANDOFF_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Handoff kind                                                             */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum trm_execution_handoff_kind {
    TRM_HANDOFF_GRID81_TO_FROZEN_TRM_EXECUTION_INPUT = 0u,
} trm_execution_handoff_kind;

/* ──────────────────────────────────────────────────────────────────── */
/* Execution handoff                                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_trm_execution_handoff_v1 {
    uint32_t                          abi_version;
    uint32_t                          handoff_kind; /* trm_execution_handoff_kind */

    /* Root query */
    hacf_digest                       root_query_overlay_digest;

    /* P7 binding */
    hacf_digest                       P7_structural_packet_digest;

    /* P8 binding */
    hacf_digest                       P8_adapter_packet_digest;
    hacf_digest                       TRM_abi_digest;
    hacf_digest                       adapter_policy_digest;
    hacf_digest                       input_tensor_digest;
    hacf_digest                       fixed_mask_digest;
    hacf_digest                       writable_mask_digest;

    /* Schema binding (P8 artifacts P9 must respect) */
    hacf_digest                       candidate_frame_schema_digest;
    hacf_digest                       output_guard_schema_digest;
    hacf_digest                       guarded_result_schema_digest;

    /* Semantic metadata (remains separate from TRM input) */
    hacf_digest                       semantic_trace_sidecar_digest;
    hacf_digest                       constraint_projection_manifest_digest;

    /* Handoff policy */
    hacf_digest                       handoff_policy_digest;

    /* HACF */
    hacf_digest                       HACF_package_digest;

    /* Handoff identity */
    hacf_digest                       handoff_digest;

    /* P9 explicit declarations */
    uint32_t                          P9_may_bind_model;         /* 1 */
    uint32_t                          P9_may_execute_model;      /* 1 */
    uint32_t                          P9_must_emit_candidate;    /* 1 */
    uint32_t                          P9_must_pass_guard;        /* 1 */
    uint32_t                          P9_may_not_mutate_P7;      /* 1 */
    uint32_t                          P9_may_not_mutate_fixed;   /* 1 */
    uint32_t                          P9_may_not_feed_sidecar;   /* 1 */
    uint32_t                          P9_may_not_define_residual; /* 1 */
    uint32_t                          P9_may_not_invoke_projector; /* 1 */
    uint32_t                          P9_may_not_grant_admission; /* 1 */

    uint8_t                           reserved[64];
} elpis_semantic_trm_execution_handoff_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                             */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize: set ABI version, handoff kind, P9 declarations, zero reserved. */
void elpis_trm_execution_handoff_init(
    elpis_semantic_trm_execution_handoff_v1 *handoff);

/* Compute handoff identity. Domain: "elpis.semantic.trm_execution_handoff.v1" */
int elpis_trm_execution_handoff_identity(
    const elpis_semantic_trm_execution_handoff_v1 *handoff, hacf_digest *out);

/* Validate: kind, P9 declarations, schema bindings, reserved zeroed. */
int elpis_trm_execution_handoff_validate(
    const elpis_semantic_trm_execution_handoff_v1 *handoff);

/* Persistence */
int elpis_write_trm_execution_handoff(const char *path,
    const elpis_semantic_trm_execution_handoff_v1 *handoff);
int elpis_read_trm_execution_handoff(const char *path,
    elpis_semantic_trm_execution_handoff_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
