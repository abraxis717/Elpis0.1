/* elpis/vector_shard.h - immutable vector shard binary format (Gate R2).
 *
 * Layout, little-endian throughout, no implicit padding:
 *
 *   [0     , 256)  header, ELPIS_VSHARD_HEADER_BYTES
 *   [256   , 256 + payload_bytes)      records, sorted by chunk digest ascending
 *   [.....,  + metadata_bytes)         namespace/authority side table
 *
 * One record is exactly ELPIS_VSHARD_RECORD_BYTES:
 *   chunk_digest[32] || doc_digest[32] || float32 vector[dimensions]
 *
 * Records carry no text. Chunk and document identities are the corpus's; the
 * shard binds to a corpus manifest digest so metadata drift is detectable.
 *
 * The reader admits nothing partially: every structural, digest and value check
 * runs before a single record is exposed. */
#ifndef ELPIS_VECTOR_SHARD_H
#define ELPIS_VECTOR_SHARD_H

#include <stddef.h>
#include <stdint.h>

#include "elpis/embedding_provider.h"

#ifdef __cplusplus
extern "C" {
#endif

#define ELPIS_VSHARD_MAGIC          "ELPVSHD1"
#define ELPIS_VSHARD_MAGIC_BYTES    8u
#define ELPIS_VSHARD_ABI_VERSION    1u
#define ELPIS_VSHARD_HEADER_BYTES   256u
#define ELPIS_VSHARD_RECORD_BYTES   (32u + 32u + ELPIS_EMBEDDING_DIM * 4u)   /* 1600 */
#define ELPIS_VSHARD_MAX_VECTORS    100000000ull

/* FMS object kind for a resident shard payload. */
#define ELPIS_FMS_KIND_VECTOR_SHARD 0x56534831u   /* 'VSH1' */

typedef struct elpis_vshard_header {
    uint32_t abi_version;
    uint32_t header_bytes;
    uint64_t vector_count;
    uint32_t dimensions;
    uint32_t element_type;
    uint32_t metric;
    uint32_t normalization;
    uint32_t record_bytes;
    uint32_t flags;
    uint64_t payload_bytes;
    uint64_t metadata_bytes;
    char     embedding_profile_digest[65];
    char     corpus_manifest_digest[65];
    char     metadata_map_digest[65];
    char     payload_digest[65];
    char     shard_digest[65];      /* digest of the whole file */
} elpis_vshard_header;

/* One logical record supplied to the builder. */
typedef struct elpis_vshard_input {
    char        chunk_digest[65];
    char        doc_digest[65];
    const char *ns;
    const char *authority;
    const float *vector;            /* dimensions floats, provider-normalized */
} elpis_vshard_input;

/* Build an immutable shard. Records are sorted by chunk digest, so identical
 * logical content yields identical bytes regardless of input order. Duplicate
 * chunk digests are rejected. The buffer is malloc'd; free with elpis_free. */
int elpis_vshard_build(const elpis_vshard_input *records, uint64_t count,
                       const elpis_embedding_profile *profile,
                       const char *corpus_manifest_digest,
                       void **bytes_out, size_t *len_out, char shard_digest_out[65]);

/* Write a built shard to path. Refuses to overwrite: shards are immutable. */
int elpis_vshard_write(const char *path, const void *bytes, size_t len);
int elpis_vshard_read_file(const char *path, void **bytes_out, size_t *len_out);

/* Full structural and cryptographic verification. Returns 0 only when every
 * check passes. reason (optional) receives a stable machine-readable code. */
int elpis_vshard_verify(const void *bytes, size_t len, elpis_vshard_header *out,
                        char *reason, size_t reason_cap);

/* Accessors valid only after a successful verify of the same buffer. */
const uint8_t *elpis_vshard_record(const void *bytes, uint64_t index);
const char    *elpis_vshard_record_chunk_hex(const void *bytes, uint64_t index, char out[65]);
const float   *elpis_vshard_record_vector(const void *bytes, uint64_t index);

/* Side-table lookup: namespace and authority for a record index. */
int elpis_vshard_record_meta(const void *bytes, size_t len, uint64_t index,
                             const char **ns_out, const char **authority_out);

/* Canonical shard manifest (stable key order, no floats). */
int elpis_vshard_manifest_json(const elpis_vshard_header *h, char **json_out, char digest_out[65]);

#ifdef __cplusplus
}
#endif
#endif
