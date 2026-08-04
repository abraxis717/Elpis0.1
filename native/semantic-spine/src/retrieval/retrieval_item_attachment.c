/* retrieval_item_attachment.c — Retrieval item attachment implementation.
 *
 * Preserves R3 transport metadata without polluting stable evidence-node
 * identity. The EVIDENCE_CHUNK node binds only chunk payload digest + flags.
 */
#include "elpis_semantic/retrieval_item_attachment.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>

static void write_be32(elpis_sha256_ctx *h, uint32_t v) {
    uint32_t be = htonl(v);
    elpis_sha256_update(h, &be, 4);
}

static void write_le32(elpis_sha256_ctx *h, uint32_t v) {
    uint8_t b[4] = {(uint8_t)v, (uint8_t)(v >> 8),
                    (uint8_t)(v >> 16), (uint8_t)(v >> 24)};
    elpis_sha256_update(h, b, 4);
}

static void write_le64(elpis_sha256_ctx *h, uint64_t v) {
    uint8_t b[8];
    for (unsigned i = 0; i < 8; ++i)
        b[i] = (uint8_t)(v >> (8u * i));
    elpis_sha256_update(h, b, 8);
}

void elpis_attachment_init(elpis_retrieval_item_attachment_v1 *att) {
    if (!att) return;
    memset(att, 0, sizeof(*att));
    att->abi_version = RETRIEVAL_ITEM_ATTACHMENT_ABI_VERSION;
}

int elpis_attachment_digest(
    const elpis_retrieval_item_attachment_v1 *att, hacf_digest *out)
{
    if (!att || !out) return SEMANTIC_E_INVAL;

    static const char domain[] = "elpis.semantic.retrieval_item_attachment.v1";
    size_t domain_len = strlen(domain);
    uint32_t be_len = htonl((uint32_t)domain_len);

    elpis_sha256_ctx h;
    elpis_sha256_init(&h);

    elpis_sha256_update(&h, &be_len, 4);
    elpis_sha256_update(&h, domain, domain_len);

    /* abi_version BE32 */
    write_be32(&h, att->abi_version);

    /* evidence_node_digest (32) */
    elpis_sha256_update(&h, att->evidence_node_digest.bytes, 32);
    /* retrieval_bundle_digest (32) */
    elpis_sha256_update(&h, att->retrieval_bundle_digest.bytes, 32);
    /* retrieval_bundle_package_digest (32) */
    elpis_sha256_update(&h, att->retrieval_bundle_package_digest.bytes, 32);
    /* retrieval_requirement_digest (32) */
    elpis_sha256_update(&h, att->retrieval_requirement_digest.bytes, 32);
    /* chunk_digest (32) */
    elpis_sha256_update(&h, att->chunk_digest.bytes, 32);
    /* document_digest (32) */
    elpis_sha256_update(&h, att->document_digest.bytes, 32);
    /* text_digest (32) */
    elpis_sha256_update(&h, att->text_digest.bytes, 32);
    /* namespace_digest (32) */
    elpis_sha256_update(&h, att->namespace_digest.bytes, 32);

    /* item_authority BE32 */
    write_be32(&h, att->item_authority);
    /* source_mask BE32 */
    write_be32(&h, att->source_mask);
    /* lexical_rank BE32 */
    write_be32(&h, att->lexical_rank);
    /* dense_rank BE32 */
    write_be32(&h, att->dense_rank);

    /* dense_score_key LE64 */
    write_le64(&h, (uint64_t)att->dense_score_key);
    /* fusion_score_key LE64 */
    write_le64(&h, att->fusion_score_key);

    /* final_rank BE32 */
    write_be32(&h, att->final_rank);
    /* item_kind BE32 */
    write_be32(&h, att->item_kind);

    /* graph_parent_digest (32) */
    elpis_sha256_update(&h, att->graph_parent_digest.bytes, 32);
    /* graph_hop BE32 */
    write_be32(&h, att->graph_hop);
    /* graph_edge_type BE32 */
    write_be32(&h, att->graph_edge_type);
    /* graph_edge_authority BE32 */
    write_be32(&h, att->graph_edge_authority);

    /* graph_edge_provenance_status BE32 */
    write_be32(&h, (uint32_t)att->graph_edge_provenance_status);

    uint8_t d[32];
    elpis_sha256_final(&h, d);
    memcpy(out->bytes, d, 32);
    return SEMANTIC_OK;
}

int elpis_attachment_validate(
    const elpis_retrieval_item_attachment_v1 *att)
{
    if (!att) return SEMANTIC_E_INVAL;
    if (att->abi_version != RETRIEVAL_ITEM_ATTACHMENT_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* Reserved zero */
    if (memcmp(att->reserved, "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0", 32) != 0)
        return SEMANTIC_E_INVAL;

    /* item_kind: 1 (PRIMARY) or 2 (CONTEXT) */
    if (att->item_kind != 1 && att->item_kind != 2)
        return SEMANTIC_E_INVAL;

    /* graph_hop: 0 or 1 */
    if (att->graph_hop > 1)
        return SEMANTIC_E_INVAL;

    /* authority 0..3 */
    if (att->item_authority > 3)
        return SEMANTIC_E_INVAL;

    /* provenance status valid */
    if (att->graph_edge_provenance_status > GRAPH_PROVENANCE_NOT_APPLICABLE)
        return SEMANTIC_E_INVAL;

    /* edge_authority 0..3 */
    if (att->graph_edge_authority > 3)
        return SEMANTIC_E_INVAL;

    return SEMANTIC_OK;
}

int elpis_attachment_is_duplicate(
    const elpis_retrieval_item_attachment_v1 *a,
    const elpis_retrieval_item_attachment_v1 *b)
{
    if (!a || !b) return SEMANTIC_E_INVAL;
    hacf_digest da, db;
    if (elpis_attachment_digest(a, &da) != SEMANTIC_OK) return SEMANTIC_E_INVAL;
    if (elpis_attachment_digest(b, &db) != SEMANTIC_OK) return SEMANTIC_E_INVAL;
    return hacf_digest_cmp(&da, &db) == 0 ? 1 : 0;
}
