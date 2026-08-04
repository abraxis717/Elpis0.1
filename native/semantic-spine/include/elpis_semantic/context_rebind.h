/* elpis_semantic/context_rebind.h — Requirement-set rebind for P5 context re-evaluation.
 *
 * P2 requirement sets bind an exact target overlay and composed view. P5 must not
 * reuse a P2 requirement-set identity against a different view. This module constructs
 * a new requirement set differing only in the exact target-view binding field.
 *
 * Identity domain: "elpis.semantic.context_rebind.v1"
 */
#ifndef ELPIS_SEMANTIC_CONTEXT_REBIND_H
#define ELPIS_SEMANTIC_CONTEXT_REBIND_H

#include "elpis_semantic/context_requirement_set.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CONTEXT_REBIND_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Rebind disposition                                                    */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum context_rebind_disposition {
    REQUIREMENT_SET_REBOUND       = 0,
    REQUIREMENT_SET_REBIND_BLOCKED_BY_VIEW       = 1,
    REQUIREMENT_SET_REBIND_BLOCKED_BY_SEMANTIC_CHANGE = 2,
    REQUIREMENT_SET_REBIND_BLOCKED_BY_IDENTITY   = 3
} context_rebind_disposition;

/* ──────────────────────────────────────────────────────────────────── */
/* Rebind receipt — proves field-by-field semantic equality except view */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_context_rebind_v1 {
    uint32_t                abi_version;

    /* Original requirement set identity */
    hacf_digest             original_requirement_set_digest;
    hacf_digest             original_query_overlay_digest;
    hacf_digest             original_composed_view_digest;

    /* New view bindings */
    hacf_digest             new_query_overlay_digest;
    hacf_digest             new_typed_evidence_view_digest;

    /* Ordered original requirement digests (preserved exactly) */
    hacf_digest             ordered_original_requirement_digests[CONTEXT_MAX_REQUIREMENTS];
    uint32_t                original_requirement_count;

    /* Ordered rebound requirement digests (new identities if view-bound) */
    hacf_digest             ordered_rebound_requirement_digests[CONTEXT_MAX_REQUIREMENTS];
    uint32_t                rebound_requirement_count;

    /* Policy digests */
    hacf_digest             original_requirement_set_policy_digest;
    hacf_digest             rebound_requirement_set_digest;
    hacf_digest             rebind_policy_digest;

    /* Final identity */
    hacf_digest             rebind_receipt_digest;

    /* Disposition */
    uint32_t                disposition; /* context_rebind_disposition */

    uint8_t                 reserved[64];
} elpis_semantic_context_rebind_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                            */
/* ──────────────────────────────────────────────────────────────────── */

/* Zero-initialize a rebind receipt. Sets abi_version. */
void elpis_context_rebind_init(elpis_semantic_context_rebind_v1 *receipt);

/* Rebind a P2 requirement set from one composed view to a new typed-evidence view.
 *
 * Preserves: requirement type, level, target object, thresholds, filters,
 *   authority floor, profile identity, neighborhood policy, requirement policy,
 *   typed extension bytes, canonical requirement ordering.
 *
 * Changes only: target_composed_view_digest → new_typed_evidence_view_digest
 *   and target_query_overlay_digest → new_query_overlay_digest.
 *
 * Rejects (returns BLOCKED_BY_SEMANTIC_CHANGE):
 *   changed threshold, changed requirement level, changed semantic target,
 *   changed authority floor, changed profile, changed policy,
 *   added/removed/reordered requirement.
 *
 * Returns SEMANTIC_OK on success with disposition = REQUIREMENT_SET_REBOUND.
 * Returns SEMANTIC_E_INVAL with disposition set on rejection.
 * Caller must provide a pre-allocated receipt. */
int elpis_context_rebind_requirement_set(
    const elpis_semantic_context_requirement_set_v1 *original_set,
    const hacf_digest *new_query_overlay_digest,
    const hacf_digest *new_typed_evidence_view_digest,
    elpis_semantic_context_rebind_v1 *receipt);

/* Compute rebind receipt identity. Domain: "elpis.semantic.context_rebind.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *   || original_requirement_set_digest(32)
 *   || original_query_overlay_digest(32)
 *   || original_composed_view_digest(32)
 *   || new_query_overlay_digest(32)
 *   || new_typed_evidence_view_digest(32)
 *   || original_requirement_count(4 BE)
 *   || for each original requirement digest: digest(32)
 *   || rebound_requirement_count(4 BE)
 *   || for each rebound requirement digest: digest(32)
 *   || original_requirement_set_policy_digest(32)
 *   || rebound_requirement_set_digest(32)
 *   || rebind_policy_digest(32). */
int elpis_context_rebind_identity(
    const elpis_semantic_context_rebind_v1 *receipt, hacf_digest *out);

/* Validate rebind receipt: known ABI, zero reserved, count consistency,
 * non-zero digests where required, valid disposition. */
int elpis_context_rebind_validate(
    const elpis_semantic_context_rebind_v1 *receipt);

/* Construct the rebound requirement set from a rebind receipt.
 * The rebound set has the same requirement digests but a new
 * target_composed_view_digest and target_query_overlay_digest.
 * Returns SEMANTIC_OK on success. Caller provides pre-allocated set. */
int elpis_context_rebind_construct_set(
    const elpis_semantic_context_rebind_v1 *receipt,
    elpis_semantic_context_requirement_set_v1 *rebound_set);

/* Verify semantic equivalence: for each original requirement, verify that
 * the corresponding rebound requirement differs only in target-view fields.
 * Returns SEMANTIC_OK if equivalent, SEMANTIC_E_INVAL with specific error
 * code if a semantic change was detected. */
int elpis_context_rebind_verify_semantic_equivalence(
    const elpis_semantic_context_rebind_v1 *receipt);

/* ──────────────────────────────────────────────────────────────────── */
/* Persistence                                                           */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_write_context_rebind(const char *path,
                                const elpis_semantic_context_rebind_v1 *receipt);
int elpis_read_context_rebind(const char *path,
                               elpis_semantic_context_rebind_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
