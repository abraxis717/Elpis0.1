/* elpis_semantic/context_iteration_state.h — Context-iteration state for P5.
 *
 * Tracks the round index, predecessor chain, and upstream digests for one
 * context-iteration sequence. Enforces monotonic round index, exact
 * predecessor chain, and fixed policy identity.
 *
 * Identity domain: "elpis.semantic.context_iteration_state.v1"
 */
#ifndef ELPIS_SEMANTIC_CONTEXT_ITERATION_STATE_H
#define ELPIS_SEMANTIC_CONTEXT_ITERATION_STATE_H

#include "elpis/cascade.h"
#include "elpis_semantic/context_iteration_policy.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CONTEXT_ITERATION_STATE_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Iteration outcome                                                     */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum context_iteration_outcome {
    OUTCOME_CONTEXT_SUFFICIENT_AND_BOUNDED_VIEW_READY = 0,
    OUTCOME_RETRIEVAL_CONTINUATION_REQUIRED           = 1,
    OUTCOME_CONTEXT_ITERATION_STOPPED_NO_PROGRESS     = 2,
    OUTCOME_CONTEXT_ITERATION_STOPPED_ROUND_LIMIT     = 3,
    OUTCOME_CONTEXT_REEVALUATION_BLOCKED              = 4,
    OUTCOME_CONTEXT_REQUIREMENT_SET_INVALID           = 5,
    OUTCOME_BOUNDED_VIEW_BLOCKED_BY_CAPACITY          = 6,
    OUTCOME_BOUNDED_VIEW_BLOCKED_BY_INTEGRITY         = 7
} context_iteration_outcome;

/* ──────────────────────────────────────────────────────────────────── */
/* Context iteration state                                               */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_context_iteration_state_v1 {
    uint32_t                abi_version;

    hacf_digest             root_query_overlay_digest;
    hacf_digest             initial_context_report_digest;
    hacf_digest             previous_iteration_state_digest;

    uint32_t                round_index;

    hacf_digest             P3_retrieval_expansion_digest;
    hacf_digest             P4_admission_layer_digest;
    hacf_digest             P4_typed_evidence_view_digest;

    hacf_digest             rebound_requirement_set_digest;
    hacf_digest             P2_reevaluation_report_digest;
    hacf_digest             P2_retrieval_requirement_bundle_digest;

    hacf_digest             progress_report_digest;

    hacf_digest             iteration_policy_digest;

    uint32_t                iteration_outcome; /* context_iteration_outcome */

    hacf_digest             iteration_state_digest;
    hacf_digest             HACF_package_digest;

    uint8_t                 reserved[64];
} elpis_semantic_context_iteration_state_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                            */
/* ──────────────────────────────────────────────────────────────────── */

/* Zero-initialize. Sets abi_version. */
void elpis_context_iteration_state_init(
    elpis_semantic_context_iteration_state_v1 *state);

/* Construct round-0 baseline state (initial pre-retrieval evaluation).
 * previous_iteration_state_digest = all-zero (no predecessor).
 * round_index = 0.
 * Returns SEMANTIC_OK on success. */
int elpis_context_iteration_state_round_zero(
    elpis_semantic_context_iteration_state_v1 *state,
    const hacf_digest *root_query_overlay_digest,
    const hacf_digest *initial_context_report_digest,
    const hacf_digest *iteration_policy_digest);

/* Construct round-N state (N >= 1) from a valid predecessor.
 * Enforces: monotonically increasing round index, same root overlay,
 *   same policy, non-cyclic predecessor.
 * Returns SEMANTIC_OK on success, SEMANTIC_E_INVAL on violation. */
int elpis_context_iteration_state_advance(
    elpis_semantic_context_iteration_state_v1 *state,
    const elpis_semantic_context_iteration_state_v1 *previous,
    const hacf_digest *P3_retrieval_expansion_digest,
    const hacf_digest *P4_admission_layer_digest,
    const hacf_digest *P4_typed_evidence_view_digest,
    const hacf_digest *rebound_requirement_set_digest,
    const hacf_digest *P2_reevaluation_report_digest,
    const hacf_digest *P2_retrieval_requirement_bundle_digest,
    const hacf_digest *progress_report_digest);

/* Compute state identity. Domain: "elpis.semantic.context_iteration_state.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *   || root_query_overlay_digest(32)
 *   || initial_context_report_digest(32)
 *   || previous_iteration_state_digest(32)
 *   || round_index(4 BE)
 *   || P3_retrieval_expansion_digest(32)
 *   || P4_admission_layer_digest(32)
 *   || P4_typed_evidence_view_digest(32)
 *   || rebound_requirement_set_digest(32)
 *   || P2_reevaluation_report_digest(32)
 *   || P2_retrieval_requirement_bundle_digest(32)
 *   || progress_report_digest(32)
 *   || iteration_policy_digest(32)
 *   || iteration_outcome(4 BE). */
int elpis_context_iteration_state_identity(
    const elpis_semantic_context_iteration_state_v1 *state, hacf_digest *out);

/* Validate: known ABI, zero reserved, monotonic round index,
 * valid predecessor chain, non-cyclic references. */
int elpis_context_iteration_state_validate(
    const elpis_semantic_context_iteration_state_v1 *state);

/* Adjudicate iteration outcome based on P2 disposition, progress,
 * and iteration policy. Returns the outcome enum value.
 *
 * Case order:
 *  1. P2 REQUIREMENT_SET_INVALID → CONTEXT_REQUIREMENT_SET_INVALID
 *  2. P2 EVALUATION_BLOCKED     → CONTEXT_REEVALUATION_BLOCKED
 *  3. P2 CONTEXT_SUFFICIENT     → CONTEXT_SUFFICIENT_AND_BOUNDED_VIEW_READY
 *  4. P2 RETRIEVAL_REQUIRED + progress + within round limit
 *                                     → RETRIEVAL_CONTINUATION_REQUIRED
 *  5. P2 RETRIEVAL_REQUIRED + no progress
 *                                     → CONTEXT_ITERATION_STOPPED_NO_PROGRESS
 *  6. round_index >= max rounds     → CONTEXT_ITERATION_STOPPED_ROUND_LIMIT */
int elpis_context_iteration_outcome_adjudicate(
    const elpis_semantic_context_iteration_state_v1 *state,
    uint32_t P2_disposition,
    uint32_t progress_disposition,
    const elpis_semantic_context_iteration_policy_v1 *policy);

/* Persistence */
int elpis_write_iteration_state(const char *path,
                                 const elpis_semantic_context_iteration_state_v1 *state);
int elpis_read_iteration_state(const char *path,
                                elpis_semantic_context_iteration_state_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
