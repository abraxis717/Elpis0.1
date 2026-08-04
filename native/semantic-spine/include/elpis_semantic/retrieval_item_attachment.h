/* elpis_semantic/retrieval_item_attachment.h — Retrieval item attachment.
 *
 * Preserves R3 transport metadata without polluting stable evidence-node
 * identity. The EVIDENCE_CHUNK node binds only chunk payload digest + flags.
 * The attachment carries all retrieval-specific metadata.
 *
 * Identity domain: "elpis.semantic.retrieval_item_attachment.v1"
 */
#ifndef ELPIS_SEMANTIC_RETRIEVAL_ITEM_ATTACHMENT_H
#define ELPIS_SEMANTIC_RETRIEVAL_ITEM_ATTACHMENT_H

#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RETRIEVAL_ITEM_ATTACHMENT_ABI_VERSION 1u

/* Graph edge provenance status */
typedef enum graph_provenance_status {
    GRAPH_PROVENANCE_PRESERVED     = 0, /* exact provenance in bundle */
    GRAPH_PROVENANCE_UNAVAILABLE   = 1, /* omitted by R3, not recovered */
    GRAPH_PROVENANCE_RECOVERED     = 2, /* uniquely recovered from bound graph */
    GRAPH_PROVENANCE_AMBIGUOUS     = 3, /* multiple matching edges */
    GRAPH_PROVENANCE_NOT_APPLICABLE = 4 /* primary item, no graph edge */
} graph_provenance_status;

/* ──────────────────────────────────────────────────────────────────── */
/* Retrieval item attachment record */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_retrieval_item_attachment_v1 {
    uint32_t                    abi_version;
    hacf_digest                 evidence_node_digest;
    hacf_digest                 retrieval_bundle_digest;
    hacf_digest                 retrieval_bundle_package_digest;
    hacf_digest                 retrieval_requirement_digest;
    hacf_digest                 chunk_digest;
    hacf_digest                 document_digest;
    hacf_digest                 text_digest;
    hacf_digest                 namespace_digest;
    uint32_t                    item_authority;          /* 0..3 numeric */
    uint32_t                    source_mask;
    uint32_t                    lexical_rank;            /* one-based; 0 = absent */
    uint32_t                    dense_rank;              /* one-based; 0 = absent */
    int64_t                     dense_score_key;
    uint64_t                    fusion_score_key;
    uint32_t                    final_rank;
    uint32_t                    item_kind;               /* PRIMARY(1) or CONTEXT(2) */
    hacf_digest                 graph_parent_digest;     /* zero for primary */
    uint32_t                    graph_hop;               /* 0 or 1 */
    uint32_t                    graph_edge_type;
    uint32_t                    graph_edge_authority;    /* 0..3 */
    graph_provenance_status     graph_edge_provenance_status;
    hacf_digest                 recovered_provenance_digest; /* valid if status==RECOVERED */
    hacf_digest                 attachment_digest;
    uint8_t                     reserved[32];
} elpis_retrieval_item_attachment_v1;

/* Zero-initialize an attachment. Sets abi_version. */
void elpis_attachment_init(elpis_retrieval_item_attachment_v1 *att);

/* Compute attachment identity digest.
 * Domain: "elpis.semantic.retrieval_item_attachment.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || evidence_node_digest(32)
 *             || retrieval_bundle_digest(32)
 *             || retrieval_bundle_package_digest(32)
 *             || retrieval_requirement_digest(32)
 *             || chunk_digest(32)
 *             || document_digest(32)
 *             || text_digest(32)
 *             || namespace_digest(32)
 *             || item_authority(4 BE)
 *             || source_mask(4 BE)
 *             || lexical_rank(4 BE)
 *             || dense_rank(4 BE)
 *             || dense_score_key(8 LE)
 *             || fusion_score_key(8 LE)
 *             || final_rank(4 BE)
 *             || item_kind(4 BE)
 *             || graph_parent_digest(32)
 *             || graph_hop(4 BE)
 *             || graph_edge_type(4 BE)
 *             || graph_edge_authority(4 BE)
 *             || graph_edge_provenance_status(4 BE). */
int elpis_attachment_digest(
    const elpis_retrieval_item_attachment_v1 *att, hacf_digest *out);

/* Validate: known ABI, zero reserved, valid enums, consistent fields. */
int elpis_attachment_validate(
    const elpis_retrieval_item_attachment_v1 *att);

/* Check if two attachments are exact duplicates (same identity). */
int elpis_attachment_is_duplicate(
    const elpis_retrieval_item_attachment_v1 *a,
    const elpis_retrieval_item_attachment_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
