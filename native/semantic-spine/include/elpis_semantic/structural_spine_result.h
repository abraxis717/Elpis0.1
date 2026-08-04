/* elpis_semantic/structural_spine_result.h — Integrated spine result v1.
 *
 * Captures the complete P5→P12 spine execution with all invariant counts.
 * Qualification requires all mutation and bypass counts to be zero.
 *
 * Identity domain: "elpis.semantic.structural_spine_result.v1"
 */
#ifndef ELPIS_SEMANTIC_STRUCTURAL_SPINE_RESULT_H
#define ELPIS_SEMANTIC_STRUCTURAL_SPINE_RESULT_H

#include "elpis_semantic/structural_spine_trace.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SPINE_RESULT_ABI_VERSION 1u
#define SPINE_RESULT_MAX_RECEIPTS 32u
#define SPINE_RESULT_MAX_COMMITTED 32u
#define SPINE_MAX_TERMINATION_REASON 64u

typedef enum spine_termination_reason {
    SPINE_TERMINATION_MAXIMUM_STEPS_REACHED = 0,
    SPINE_TERMINATION_GUARD_REJECTED = 1,
    SPINE_TERMINATION_NO_MORE_IMPROVEMENT = 2,
    SPINE_TERMINATION_EXACTLY_SOLVED = 3,
} spine_termination_reason;

typedef struct elpis_semantic_structural_spine_result_v1 {
    uint32_t                          abi_version;

    /* Replay identity chain */
    hacf_digest                       request_digest;
    hacf_digest                       P6_topology_ir_digest;
    hacf_digest                       P7_structural_packet_digest;
    hacf_digest                       P8_mutability_digest;
    hacf_digest                       P12_integration_result_digest;

    /* Structural state */
    hacf_digest                       initial_structural_state_digest;
    hacf_digest                       final_structural_state_digest;

    /* Ordered receipt digests */
    hacf_digest                       boundary_receipt_digests[SPINE_RESULT_MAX_RECEIPTS];
    uint32_t                          boundary_receipt_count;
    hacf_digest                       committed_state_digests[SPINE_RESULT_MAX_COMMITTED];
    uint32_t                          committed_state_count;

    /* Observation */
    hacf_digest                       final_observation_manifest_digest;

    /* Invariant counts — must all be zero for qualification */
    uint32_t                          semantic_mutation_count;
    uint32_t                          semantic_relation_invention_count;
    uint32_t                          semantic_relation_loss_count;
    uint32_t                          authority_change_count;
    uint32_t                          fixed_cell_mutation_count;
    uint32_t                          unguarded_committed_step_count;

    /* Execution summary */
    uint32_t                          initial_filled_cells;
    uint32_t                          final_filled_cells;
    uint32_t                          backend_invocation_count;
    uint32_t                          termination_reason;   /* spine_termination_reason */
    char                              termination_reason_str[SPINE_MAX_TERMINATION_REASON];

    /* Complete trace */
    elpis_semantic_structural_spine_trace_v1 complete_trace;
    hacf_digest                       complete_trace_digest;

    /* Result identity */
    hacf_digest                       result_digest;
    hacf_digest                       HACF_package_digest;

    uint8_t                           reserved[128];
} elpis_semantic_structural_spine_result_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_spine_result_init(
    elpis_semantic_structural_spine_result_v1 *result);
int elpis_spine_result_identity(
    const elpis_semantic_structural_spine_result_v1 *result, hacf_digest *out);
int elpis_spine_result_validate(
    const elpis_semantic_structural_spine_result_v1 *result);
int elpis_spine_result_is_qualified(
    const elpis_semantic_structural_spine_result_v1 *result);
int elpis_spine_result_add_committed_state(
    elpis_semantic_structural_spine_result_v1 *result,
    const hacf_digest *digest);

#ifdef __cplusplus
}
#endif

#endif /* ELPIS_SEMANTIC_STRUCTURAL_SPINE_RESULT_H */
