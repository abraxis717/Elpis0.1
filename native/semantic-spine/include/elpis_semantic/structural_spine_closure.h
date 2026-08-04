/* elpis_semantic/structural_spine_closure.h — Structural spine closure v1.
 *
 * Immutable closure manifest for the P5→P12 Semantic Fabric structural spine.
 * Requires all invariant counts = 0 and runtime_admission = false.
 *
 * Identity domain: "elpis.semantic.structural_spine_closure.v1"
 */
#ifndef ELPIS_SEMANTIC_STRUCTURAL_SPINE_CLOSURE_H
#define ELPIS_SEMANTIC_STRUCTURAL_SPINE_CLOSURE_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SPINE_CLOSURE_ABI_VERSION 1u

typedef enum spine_closure_kind {
    SPINE_CLOSURE_ELPIS_SEMANTIC_STRUCTURAL_SPINE_V1 = 0,
} spine_closure_kind;

typedef enum spine_closure_disposition {
    SPINE_CLOSURE_QUALIFIED = 0,
    SPINE_CLOSURE_BLOCKED = 1,
} spine_closure_disposition;

typedef struct elpis_semantic_structural_spine_closure_v1 {
    uint32_t                          abi_version;
    uint32_t                          closure_kind;   /* spine_closure_kind */

    /* Bound phase digests */
    hacf_digest                       P5_root_digest;
    hacf_digest                       P6_topology_ir_digest;
    hacf_digest                       P7_structural_packet_digest;
    hacf_digest                       P8_mutability_digest;
    hacf_digest                       P12_integration_handoff_digest;

    /* Policy and execution */
    hacf_digest                       spine_policy_digest;
    hacf_digest                       integrated_request_digest;
    hacf_digest                       integrated_result_digest;

    /* Verification receipts */
    hacf_digest                       production_replay_digest;
    hacf_digest                       sidecar_roundtrip_digest;
    hacf_digest                       invariant_receipt_digest;
    hacf_digest                       P10_regression_digest;
    hacf_digest                       determinism_receipt_digest;
    hacf_digest                       sanitizer_receipt_digest;
    hacf_digest                       nonregression_receipt_digest;

    /* Invariant counts — must all be zero */
    uint32_t                          semantic_mutation_count;
    uint32_t                          semantic_relation_invention_count;
    uint32_t                          semantic_relation_loss_count;
    uint32_t                          authority_change_count;
    uint32_t                          fixed_cell_mutation_count;
    uint32_t                          unguarded_commit_count;

    /* Runtime admission — must be false */
    int                               runtime_admission;

    /* Closure identity */
    uint32_t                          closure_disposition;  /* spine_closure_disposition */
    hacf_digest                       closure_digest;
    hacf_digest                       HACF_package_digest;

    uint8_t                           reserved[128];
} elpis_semantic_structural_spine_closure_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_spine_closure_init(
    elpis_semantic_structural_spine_closure_v1 *closure);
int elpis_spine_closure_identity(
    const elpis_semantic_structural_spine_closure_v1 *closure, hacf_digest *out);
int elpis_spine_closure_validate(
    const elpis_semantic_structural_spine_closure_v1 *closure);
int elpis_spine_closure_is_qualified(
    const elpis_semantic_structural_spine_closure_v1 *closure);

#ifdef __cplusplus
}
#endif

#endif /* ELPIS_SEMANTIC_STRUCTURAL_SPINE_CLOSURE_H */
