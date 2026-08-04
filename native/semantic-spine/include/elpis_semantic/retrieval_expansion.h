/* elpis_semantic/retrieval_expansion.h — Immutable retrieval expansion.
 *
 * Creates an immutable retrieval-expansion layer over the original query
 * overlay. Does NOT mutate the original base snapshot or query overlay.
 *
 * Identity domain: "elpis.semantic.retrieval_expansion.v1"
 * Expanded view identity domain: "elpis.semantic.retrieval_expanded_view.v1"
 */
#ifndef ELPIS_SEMANTIC_RETRIEVAL_EXPANSION_H
#define ELPIS_SEMANTIC_RETRIEVAL_EXPANSION_H

#include "elpis_semantic/retrieval_item_attachment.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RETRIEVAL_EXPANSION_ABI_VERSION 1u
#define MAX_BRIDGE_RECEIPTS 256u
#define MAX_BUNDLE_DIGESTS  256u
#define MAX_EVIDENCE_NODES  1024u

/* ──────────────────────────────────────────────────────────────────── */
/* Retrieval expansion record */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_retrieval_expansion_v1 {
    uint32_t                    abi_version;
    hacf_digest                 base_snapshot_digest;
    hacf_digest                 original_query_overlay_digest;
    hacf_digest                 original_composed_view_digest;
    hacf_digest                 p2_deficit_report_digest;
    hacf_digest                 p2_requirement_bundle_digest;
    hacf_digest                 bridge_receipt_digests[MAX_BRIDGE_RECEIPTS];
    uint32_t                    bridge_receipt_count;
    hacf_digest                 bundle_digests[MAX_BUNDLE_DIGESTS];
    hacf_digest                 bundle_package_digests[MAX_BUNDLE_DIGESTS];
    uint32_t                    bundle_count;
    hacf_digest                 transport_registry_digest;
    hacf_digest                 evidence_segment_digest;
    hacf_digest                 attachment_collection_digest;
    hacf_digest                 expansion_policy_digest;
    hacf_digest                 retrieval_expansion_digest;
    uint8_t                     reserved[32];
} elpis_retrieval_expansion_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Expanded read-only view */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_retrieval_expanded_view_v1 {
    uint32_t                    abi_version;
    hacf_digest                 base_snapshot_digest;
    hacf_digest                 query_overlay_digest;
    hacf_digest                 retrieval_expansion_digest;
    hacf_digest                 embedding_collections_digest; /* P1 collections identity */
    hacf_digest                 expanded_view_policy_digest;
    hacf_digest                 expanded_view_digest;
    uint8_t                     reserved[32];
} elpis_retrieval_expanded_view_v1;

/* Initialize expansion. Sets abi_version, zeroes reserved. */
void elpis_retrieval_expansion_init(elpis_retrieval_expansion_v1 *exp);

/* Compute retrieval expansion identity digest. */
int elpis_retrieval_expansion_digest(
    const elpis_retrieval_expansion_v1 *exp, hacf_digest *out);

/* Validate expansion: known ABI, zero reserved, consistent counts, nonzero digests. */
int elpis_retrieval_expansion_validate(
    const elpis_retrieval_expansion_v1 *exp);

/* Initialize expanded view. Sets abi_version. */
void elpis_retrieval_expanded_view_init(elpis_retrieval_expanded_view_v1 *view);

/* Compute expanded view identity digest. */
int elpis_retrieval_expanded_view_digest(
    const elpis_retrieval_expanded_view_v1 *view, hacf_digest *out);

/* Validate expanded view. */
int elpis_retrieval_expanded_view_validate(
    const elpis_retrieval_expanded_view_v1 *view);

/* Build the retrieval expansion from P2 bundle, bridge receipts, and ingest results.
 * Does not mutate base snapshot or query overlay. */
int elpis_build_retrieval_expansion(
    elpis_retrieval_expansion_v1 *exp,
    const hacf_digest *base_snapshot,
    const hacf_digest *query_overlay,
    const hacf_digest *composed_view,
    const hacf_digest *p2_deficit_report,
    const hacf_digest *p2_requirement_bundle,
    const hacf_digest *bridge_receipts[],
    uint32_t bridge_receipt_count,
    const hacf_digest *bundle_digests,
    const hacf_digest *bundle_package_digests,
    uint32_t bundle_count,
    const hacf_digest *transport_registry,
    const hacf_digest *evidence_segment,
    const hacf_digest *attachment_collection,
    const hacf_digest *expansion_policy);

/* Build the expanded read-only view. */
int elpis_build_expanded_view(
    elpis_retrieval_expanded_view_v1 *view,
    const hacf_digest *base_snapshot,
    const hacf_digest *query_overlay,
    const elpis_retrieval_expansion_v1 *expansion,
    const hacf_digest *embedding_collections,
    const hacf_digest *expanded_view_policy);

#ifdef __cplusplus
}
#endif
#endif
