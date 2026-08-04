#ifndef ELPIS_CHUNKING_H
#define ELPIS_CHUNKING_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ELPIS_MT_TEXT     "text/plain"
#define ELPIS_MT_MARKDOWN "text/markdown"
#define ELPIS_MT_CODE     "text/x-source"
#define ELPIS_MT_JSON     "application/json"
#define ELPIS_MT_JSONL    "application/x-ndjson"

typedef struct elpis_chunk_profile {
    char     name[64];
    uint32_t target_bytes;
    uint32_t max_bytes;
    uint32_t min_bytes;
    uint32_t version;
} elpis_chunk_profile;

typedef struct elpis_chunk {
    char     digest[65];
    char     norm_digest[65];
    uint64_t ordinal;
    uint64_t byte_start;
    uint64_t byte_end;
} elpis_chunk;

void   elpis_chunk_profile_default(elpis_chunk_profile *p);
int    elpis_chunk_profile_validate(const elpis_chunk_profile *p);
int    elpis_chunk_profile_digest_checked(const elpis_chunk_profile *p,
                                           const char *media_type,
                                           char out[65]);
void   elpis_chunk_profile_digest(const elpis_chunk_profile *p,
                                  const char *media_type,
                                  char out[65]);
size_t elpis_normalize(const char *in, size_t len, char *out, size_t out_cap);
int    elpis_chunk_document(const void *bytes, size_t len, const char *media_type,
                            const elpis_chunk_profile *p, const char *doc_digest,
                            elpis_chunk **out, size_t *n_out);
void   elpis_chunks_free(elpis_chunk *chunks);

#ifdef __cplusplus
}
#endif

#endif
