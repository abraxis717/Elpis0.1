#ifndef ELPIS_CORPUS_H
#define ELPIS_CORPUS_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct elpis_corpus elpis_corpus;

typedef struct elpis_ingest_meta {
    const char *ns;
    const char *authority;
    const char *media_type;
    const char *origin;
} elpis_ingest_meta;

typedef struct elpis_ingest_result {
    char     doc_digest[65];
    uint32_t chunk_count;
    uint8_t  duplicate;
} elpis_ingest_result;

typedef struct elpis_hit {
    char   doc_digest[65];
    char   chunk_digest[65];
    char   ns[96];
    char   authority[32];
    double lexical_score;
    uint64_t ordinal;
    uint64_t byte_start;
    uint64_t byte_end;
} elpis_hit;

int         elpis_corpus_open(const char *state_root, elpis_corpus **out);
void        elpis_corpus_close(elpis_corpus *c);
const char *elpis_corpus_error(const elpis_corpus *c);

int elpis_corpus_ingest_bytes(elpis_corpus *c, const void *bytes, size_t len,
                              const elpis_ingest_meta *meta,
                              elpis_ingest_result *out);
int elpis_corpus_counts(elpis_corpus *c, uint64_t *documents, uint64_t *chunks);
int elpis_corpus_search_lexical(elpis_corpus *c, const char *query,
                                const char *namespace_filter,
                                const char *authority_filter,
                                uint32_t limit, elpis_hit *hits,
                                uint32_t *hit_count);
int elpis_corpus_document_bytes(elpis_corpus *c, const char *doc_digest,
                                void **bytes, size_t *len);
int elpis_corpus_chunk_text(elpis_corpus *c, const char *chunk_digest,
                            char **text);
int elpis_corpus_verify(elpis_corpus *c, uint64_t *ok, uint64_t *bad,
                        char *first_bad_digest, size_t first_bad_cap);
/* --- Additive R2 hook -------------------------------------------------------
 * The vector layer must bind every vector to an existing corpus chunk identity
 * and cannot do so without enumeration: ingest returns only a document digest
 * and a count, and lexical search returns only query matches. This is the sole
 * addition R2 makes to the sealed corpus ABI. It is read-only and changes no
 * existing function, table or behaviour. Enumeration order is chunk digest
 * ascending, so a shard built from it is host-independent. */
typedef struct elpis_chunk_ref {
    char     chunk_digest[65];
    char     doc_digest[65];
    char     ns[96];
    char     authority[32];
    uint64_t ordinal;
    uint64_t byte_start;
    uint64_t byte_end;
} elpis_chunk_ref;

int elpis_corpus_list_chunks(elpis_corpus *c, const char *namespace_filter,
                             const char *authority_filter, uint64_t offset,
                             uint32_t limit, elpis_chunk_ref *out, uint32_t *n_out);

/* Gate R3 additive lookup: resolve one canonical chunk identity without
 * enumerating the corpus. Read-only; returns -1 for malformed or absent IDs. */
int elpis_corpus_chunk_lookup(elpis_corpus *c, const char *chunk_digest,
                              elpis_chunk_ref *out);

int elpis_corpus_manifest_json(elpis_corpus *c, char **json, char digest[65]);
int elpis_corpus_manifest_write(elpis_corpus *c, const char *path,
                                char digest[65]);
void elpis_free(void *p);

#ifdef __cplusplus
}
#endif

#endif
