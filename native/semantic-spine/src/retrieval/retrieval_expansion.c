/* retrieval_expansion.c — Immutable retrieval expansion implementation.
 *
 * Creates an immutable retrieval-expansion layer over the original query
 * overlay. Does NOT mutate the original base snapshot or query overlay.
 */
#include "elpis_semantic/retrieval_expansion.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>

static void write_be32(elpis_sha256_ctx *h, uint32_t v) {
    uint32_t be = htonl(v);
    elpis_sha256_update(h, &be, 4);
}

void elpis_retrieval_expansion_init(elpis_retrieval_expansion_v1 *exp) {
    if (!exp) return;
    memset(exp, 0, sizeof(*exp));
    exp->abi_version = RETRIEVAL_EXPANSION_ABI_VERSION;
}

int elpis_retrieval_expansion_digest(
    const elpis_retrieval_expansion_v1 *exp, hacf_digest *out)
{
    if (!exp || !out) return SEMANTIC_E_INVAL;

    static const char domain[] = "elpis.semantic.retrieval_expansion.v1";
    size_t domain_len = strlen(domain);
    uint32_t be_len = htonl((uint32_t)domain_len);

    elpis_sha256_ctx h;
    elpis_sha256_init(&h);

    elpis_sha256_update(&h, &be_len, 4);
    elpis_sha256_update(&h, domain, domain_len);

    /* abi_version BE32 */
    write_be32(&h, exp->abi_version);

    /* base_snapshot_digest (32) */
    elpis_sha256_update(&h, exp->base_snapshot_digest.bytes, 32);
    /* original_query_overlay_digest (32) */
    elpis_sha256_update(&h, exp->original_query_overlay_digest.bytes, 32);
    /* original_composed_view_digest (32) */
    elpis_sha256_update(&h, exp->original_composed_view_digest.bytes, 32);
    /* p2_deficit_report_digest (32) */
    elpis_sha256_update(&h, exp->p2_deficit_report_digest.bytes, 32);
    /* p2_requirement_bundle_digest (32) */
    elpis_sha256_update(&h, exp->p2_requirement_bundle_digest.bytes, 32);

    /* bridge_receipt_count BE32 */
    write_be32(&h, exp->bridge_receipt_count);
    /* bridge receipt digests */
    for (uint32_t i = 0; i < exp->bridge_receipt_count; i++)
        elpis_sha256_update(&h, exp->bridge_receipt_digests[i].bytes, 32);

    /* bundle_count BE32 */
    write_be32(&h, exp->bundle_count);
    /* bundle digests */
    for (uint32_t i = 0; i < exp->bundle_count; i++) {
        elpis_sha256_update(&h, exp->bundle_digests[i].bytes, 32);
        elpis_sha256_update(&h, exp->bundle_package_digests[i].bytes, 32);
    }

    /* transport_registry_digest (32) */
    elpis_sha256_update(&h, exp->transport_registry_digest.bytes, 32);
    /* evidence_segment_digest (32) */
    elpis_sha256_update(&h, exp->evidence_segment_digest.bytes, 32);
    /* attachment_collection_digest (32) */
    elpis_sha256_update(&h, exp->attachment_collection_digest.bytes, 32);
    /* expansion_policy_digest (32) */
    elpis_sha256_update(&h, exp->expansion_policy_digest.bytes, 32);

    uint8_t d[32];
    elpis_sha256_final(&h, d);
    memcpy(out->bytes, d, 32);
    return SEMANTIC_OK;
}

int elpis_retrieval_expansion_validate(
    const elpis_retrieval_expansion_v1 *exp)
{
    if (!exp) return SEMANTIC_E_INVAL;
    if (exp->abi_version != RETRIEVAL_EXPANSION_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    if (memcmp(exp->reserved, "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0", 32) != 0)
        return SEMANTIC_E_INVAL;

    if (exp->bridge_receipt_count > MAX_BRIDGE_RECEIPTS)
        return SEMANTIC_E_INVAL;
    if (exp->bundle_count > MAX_BUNDLE_DIGESTS)
        return SEMANTIC_E_INVAL;

    /* Base snapshot must be nonzero */
    {
        uint8_t zero[32];
        memset(zero, 0, 32);
        if (memcmp(exp->base_snapshot_digest.bytes, zero, 32) == 0)
            return SEMANTIC_E_INVAL;
        if (memcmp(exp->original_query_overlay_digest.bytes, zero, 32) == 0)
            return SEMANTIC_E_INVAL;
    }

    return SEMANTIC_OK;
}

void elpis_retrieval_expanded_view_init(elpis_retrieval_expanded_view_v1 *view) {
    if (!view) return;
    memset(view, 0, sizeof(*view));
    view->abi_version = RETRIEVAL_EXPANSION_ABI_VERSION;
}

int elpis_retrieval_expanded_view_digest(
    const elpis_retrieval_expanded_view_v1 *view, hacf_digest *out)
{
    if (!view || !out) return SEMANTIC_E_INVAL;

    static const char domain[] = "elpis.semantic.retrieval_expanded_view.v1";
    size_t domain_len = strlen(domain);
    uint32_t be_len = htonl((uint32_t)domain_len);

    elpis_sha256_ctx h;
    elpis_sha256_init(&h);

    elpis_sha256_update(&h, &be_len, 4);
    elpis_sha256_update(&h, domain, domain_len);

    /* abi_version BE32 */
    write_be32(&h, view->abi_version);

    /* base_snapshot_digest (32) */
    elpis_sha256_update(&h, view->base_snapshot_digest.bytes, 32);
    /* query_overlay_digest (32) */
    elpis_sha256_update(&h, view->query_overlay_digest.bytes, 32);
    /* retrieval_expansion_digest (32) */
    elpis_sha256_update(&h, view->retrieval_expansion_digest.bytes, 32);
    /* embedding_collections_digest (32) */
    elpis_sha256_update(&h, view->embedding_collections_digest.bytes, 32);
    /* expanded_view_policy_digest (32) */
    elpis_sha256_update(&h, view->expanded_view_policy_digest.bytes, 32);

    uint8_t d[32];
    elpis_sha256_final(&h, d);
    memcpy(out->bytes, d, 32);
    return SEMANTIC_OK;
}

int elpis_retrieval_expanded_view_validate(
    const elpis_retrieval_expanded_view_v1 *view)
{
    if (!view) return SEMANTIC_E_INVAL;
    if (view->abi_version != RETRIEVAL_EXPANSION_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    if (memcmp(view->reserved, "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0", 32) != 0)
        return SEMANTIC_E_INVAL;

    /* Base snapshot must be nonzero */
    {
        uint8_t zero[32];
        memset(zero, 0, 32);
        if (memcmp(view->base_snapshot_digest.bytes, zero, 32) == 0)
            return SEMANTIC_E_INVAL;
    }

    return SEMANTIC_OK;
}

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
    const hacf_digest *expansion_policy)
{
    if (!exp || !base_snapshot || !query_overlay || !composed_view ||
        !p2_deficit_report || !p2_requirement_bundle)
        return SEMANTIC_E_INVAL;

    if (bridge_receipt_count > MAX_BRIDGE_RECEIPTS ||
        bundle_count > MAX_BUNDLE_DIGESTS)
        return SEMANTIC_E_INVAL;

    elpis_retrieval_expansion_init(exp);

    exp->base_snapshot_digest = *base_snapshot;
    exp->original_query_overlay_digest = *query_overlay;
    exp->original_composed_view_digest = *composed_view;
    exp->p2_deficit_report_digest = *p2_deficit_report;
    exp->p2_requirement_bundle_digest = *p2_requirement_bundle;

    exp->bridge_receipt_count = bridge_receipt_count;
    for (uint32_t i = 0; i < bridge_receipt_count; i++)
        exp->bridge_receipt_digests[i] = *bridge_receipts[i];

    exp->bundle_count = bundle_count;
    for (uint32_t i = 0; i < bundle_count; i++) {
        exp->bundle_digests[i] = bundle_digests[i];
        exp->bundle_package_digests[i] = bundle_package_digests[i];
    }

    if (transport_registry)
        exp->transport_registry_digest = *transport_registry;
    if (evidence_segment)
        exp->evidence_segment_digest = *evidence_segment;
    if (attachment_collection)
        exp->attachment_collection_digest = *attachment_collection;
    if (expansion_policy)
        exp->expansion_policy_digest = *expansion_policy;

    /* Compute expansion digest */
    return elpis_retrieval_expansion_digest(exp, &exp->retrieval_expansion_digest);
}

int elpis_build_expanded_view(
    elpis_retrieval_expanded_view_v1 *view,
    const hacf_digest *base_snapshot,
    const hacf_digest *query_overlay,
    const elpis_retrieval_expansion_v1 *expansion,
    const hacf_digest *embedding_collections,
    const hacf_digest *expanded_view_policy)
{
    if (!view || !base_snapshot || !query_overlay || !expansion)
        return SEMANTIC_E_INVAL;

    elpis_retrieval_expanded_view_init(view);

    view->base_snapshot_digest = *base_snapshot;
    view->query_overlay_digest = *query_overlay;
    view->retrieval_expansion_digest = expansion->retrieval_expansion_digest;

    if (embedding_collections)
        view->embedding_collections_digest = *embedding_collections;
    if (expanded_view_policy)
        view->expanded_view_policy_digest = *expanded_view_policy;

    /* Compute expanded view digest */
    return elpis_retrieval_expanded_view_digest(view, &view->expanded_view_digest);
}
