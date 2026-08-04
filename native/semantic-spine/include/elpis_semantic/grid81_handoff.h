/* elpis_semantic/grid81_handoff.h — P8 TRM adapter handoff ABI v1.
 *
 * Binds P7 structural packet and compile receipt for downstream TRM
 * adapter consumption. Explicitly declares boundaries and nonauthority.
 *
 * Identity domain: "elpis.semantic.grid81_handoff.v1"
 */
#ifndef ELPIS_SEMANTIC_GRID81_HANDOFF_H
#define ELPIS_SEMANTIC_GRID81_HANDOFF_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GRID81_HANDOFF_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Handoff kind                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum grid81_handoff_kind {
    GRID81_TO_TRM_ADAPTER_INPUT = 0,
} grid81_handoff_kind;

/* ──────────────────────────────────────────────────────────────────── */
/* Handoff record                                                       */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_grid81_handoff_v1 {
    uint32_t                          abi_version;
    uint32_t                          handoff_kind; /* grid81_handoff_kind */

    /* Root query overlay from P5 */
    hacf_digest                       root_query_overlay_digest;

    /* P6 binding */
    hacf_digest                       P6_topology_handoff_digest;

    /* P7 outputs */
    hacf_digest                       P7_structural_packet_digest;
    hacf_digest                       P7_compile_receipt_digest;

    /* Policy and template */
    hacf_digest                       grid81_policy_digest;
    hacf_digest                       grid81_codebook_digest;
    hacf_digest                       sudoku_template_digest;

    /* Tensor digests */
    hacf_digest                       digit_array_digest;
    hacf_digest                       digit_class_tensor_digest;
    hacf_digest                       occupied_mask_digest;
    hacf_digest                       compiler_writable_mask_digest;

    /* Sidecar digests */
    hacf_digest                       capsule_manifest_digest;
    hacf_digest                       trace_sidecar_digest;
    hacf_digest                       constraint_projection_manifest_digest;

    /* Authority chain */
    hacf_digest                       type_registry_chain_digest;
    hacf_digest                       authority_registry_digest;
    hacf_digest                       handoff_policy_digest;

    /* Handoff identity */
    hacf_digest                       handoff_digest;
    hacf_digest                       HACF_package_digest;

    /* Explicit P8 boundaries */
    uint32_t                          digits_are_sudoku_structural;     /* 1 */
    uint32_t                          writable_mask_is_compiler_fixed;  /* 1 */
    uint32_t                          P8_may_derive_nonzero_writable;   /* 1, with policy */
    uint32_t                          P8_may_adapt_digit_classes;       /* 1 */
    uint32_t                          P8_may_not_change_relation_id;    /* 1 */
    uint32_t                          P8_may_not_change_authority;      /* 1 */
    uint32_t                          P8_may_not_discard_conflict;      /* 1 */
    uint32_t                          P8_may_not_use_adjacency_as_proof; /* 1 */
    uint32_t                          P8_may_not_invent_residual81;     /* 1 */
    uint32_t                          P8_needs_separate_projector_qual; /* 1 */

    uint8_t                           reserved[64];
} elpis_semantic_grid81_handoff_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize handoff. Sets abi_version, handoff_kind, boundary flags. */
void elpis_grid81_handoff_init(elpis_semantic_grid81_handoff_v1 *handoff);

/* Compute handoff identity. Domain: "elpis.semantic.grid81_handoff.v1" */
int elpis_grid81_handoff_identity(
    const elpis_semantic_grid81_handoff_v1 *handoff, hacf_digest *out);

/* Validate: ABI, kind, boundaries set, digests present, reserved zeroed. */
int elpis_grid81_handoff_validate(
    const elpis_semantic_grid81_handoff_v1 *handoff);

/* Persistence */
int elpis_write_grid81_handoff(const char *path,
    const elpis_semantic_grid81_handoff_v1 *handoff);
int elpis_read_grid81_handoff(const char *path,
    elpis_semantic_grid81_handoff_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
