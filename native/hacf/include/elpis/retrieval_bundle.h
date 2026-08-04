/* elpis/retrieval_bundle.h - frozen evidence handoff produced by Gate R3. */
#ifndef ELPIS_RETRIEVAL_BUNDLE_H
#define ELPIS_RETRIEVAL_BUNDLE_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ELPIS_RETRIEVAL_BUNDLE_ABI_VERSION 1u
#define ELPIS_RETRIEVAL_BUNDLE_SCHEMA      "elpis.retrieval_bundle.v1"

#define ELPIS_RSRC_LEXICAL 0x01u
#define ELPIS_RSRC_DENSE   0x02u
#define ELPIS_RSRC_GRAPH   0x04u

#define ELPIS_RITEM_PRIMARY 1u
#define ELPIS_RITEM_CONTEXT 2u

typedef struct elpis_retrieval_bundle elpis_retrieval_bundle;

typedef struct elpis_retrieval_item_view {
    char     chunk_digest[65];
    char     doc_digest[65];
    char     ns[96];
    char     authority[32];
    char     graph_parent_digest[65]; /* all-zero hex for primary evidence */
    char     text_digest[65];
    uint64_t fusion_score_key;
    int64_t  dense_score_key;
    uint32_t lexical_rank;           /* one-based; 0 means absent */
    uint32_t dense_rank;             /* one-based; 0 means absent */
    uint32_t final_rank;             /* zero-based bundle order */
    uint32_t source_mask;
    uint32_t item_kind;
    uint32_t graph_hop;              /* 0 or 1 in R3 */
    uint32_t edge_type;
    uint32_t edge_authority;
    const char *text;                /* valid until bundle destruction */
    uint32_t text_bytes;
} elpis_retrieval_item_view;

void     elpis_retrieval_bundle_destroy(elpis_retrieval_bundle *b);
uint32_t elpis_retrieval_bundle_item_count(const elpis_retrieval_bundle *b);
int      elpis_retrieval_bundle_item(const elpis_retrieval_bundle *b, uint32_t index,
                                     elpis_retrieval_item_view *out);

int elpis_retrieval_bundle_identity(const elpis_retrieval_bundle *b,
                                    char query_digest[65],
                                    char corpus_manifest_digest[65],
                                    char vector_index_manifest_digest[65],
                                    char graph_snapshot_digest[65],
                                    char fusion_policy_digest[65],
                                    char bundle_digest[65],
                                    char hacf_package_digest[65]);

/* Canonical JSON is the frozen evidence payload. It includes exact query bytes,
 * exact chunk text, integer ranks and score keys, and all dependency digests.
 * No host float enters its identity. */
int elpis_retrieval_bundle_json(const elpis_retrieval_bundle *b,
                                char **json_out, char digest_out[65]);

/* Immutable O_EXCL export with file+directory fsync. */
int elpis_retrieval_bundle_write(const elpis_retrieval_bundle *b, const char *path,
                                 char digest_out[65]);

#ifdef __cplusplus
}
#endif
#endif
