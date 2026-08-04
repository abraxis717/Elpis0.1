/* elpis/vector_index.h - exact dense vector index over FMS-resident shards.
 *
 * Residency contract (Gate R2 is CPU-only):
 *   verified shard bytes -> fms_register(kind=ELPIS_FMS_KIND_VECTOR_SHARD)
 *   -> fms_lease_acquire(FMS_WARM, FMS_READ) for the duration of scoring
 *   -> fms_lease_release() on every path, success or failure
 *   -> the shard is demotable again
 *
 * FMS_HOT is never requested anywhere in this layer. */
#ifndef ELPIS_VECTOR_INDEX_H
#define ELPIS_VECTOR_INDEX_H

#include <stddef.h>
#include <stdint.h>

#include "elpis/embedding_provider.h"
#include "elpis/fms.h"
#include "elpis/vector_result.h"
#include "elpis/vector_shard.h"

#ifdef __cplusplus
extern "C" {
#endif

#define ELPIS_VINDEX_ABI_VERSION 1u
#define ELPIS_VINDEX_MAX_SHARDS  64u

typedef struct elpis_vector_index elpis_vector_index;

typedef struct elpis_vector_query {
    const float *vector;            /* dimensions floats */
    uint32_t     dimensions;
    uint32_t     k;
    const char  *ns_filter;         /* NULL = no filter */
    const char  *authority_filter;  /* NULL = no filter */
} elpis_vector_query;

/* fms must outlive the index. The index never destroys it.
 * Searchable indexes require ELPIS_NORM_L2. ELPIS_NORM_NONE may qualify a
 * provider in isolation but is rejected here with ELPIS_VEC_E_PROFILE.
 * corpus_manifest_digest binds admission: a shard built against a different
 * corpus manifest is refused. Pass NULL to accept any (tests only). */
int  elpis_vector_index_create(fms_ctx *fms, const elpis_embedding_profile *profile,
                               const char *corpus_manifest_digest,
                               elpis_vector_index **out);
void elpis_vector_index_destroy(elpis_vector_index *ix);
/* Last-error accessors are per calling thread, errno-style: a concurrent search
 * on another thread never overwrites this thread's diagnosis. */
/* Human-readable detail of the last failure. */
const char *elpis_vector_index_error(const elpis_vector_index *ix);
/* Structured last failure: elpis_vec_status plus the preserved fms_status cause. */
const elpis_vec_error *elpis_vector_index_last_error(const elpis_vector_index *ix);

/* Verify, then admit. Duplicate chunk digests across admitted shards are
 * rejected: no silent deduplication, no duplicate hits. */
int  elpis_vector_index_add_shard_bytes(elpis_vector_index *ix, const void *bytes, size_t len,
                                        char shard_digest_out[65]);
int  elpis_vector_index_add_shard_file(elpis_vector_index *ix, const char *path,
                                       char shard_digest_out[65]);
int  elpis_vector_index_close_shard(elpis_vector_index *ix, const char *shard_digest);

uint32_t elpis_vector_index_shard_count(const elpis_vector_index *ix);
int  elpis_vector_index_list_shards(const elpis_vector_index *ix, char (*out)[65], uint32_t cap,
                                    uint32_t *n_out);
int  elpis_vector_index_verify(elpis_vector_index *ix, const char *shard_digest);
/* FMS object backing a shard, for telemetry and residency assertions. */
int  elpis_vector_index_shard_object(const elpis_vector_index *ix, const char *shard_digest,
                                     fms_id *out);
int  elpis_vector_index_inspect(elpis_vector_index *ix, const char *shard_digest,
                                elpis_vshard_header *out);

/* Exhaustive exact search across every admitted shard. Shard order never
 * affects the result. hits must hold at least q->k entries. */
int  elpis_vector_index_search(elpis_vector_index *ix, const elpis_vector_query *q,
                               elpis_vector_hit *hits, uint32_t *n_out);

/* Digests this index binds to. corpus_digest_out receives all-zero hex when the
 * index was created unbound (tests only). */
int  elpis_vector_index_profile_digest(const elpis_vector_index *ix, char profile_digest_out[65],
                                       char corpus_digest_out[65]);

/* Canonical index manifest: shard digests sorted, no floats, stable key order. */
int  elpis_vector_index_manifest_json(elpis_vector_index *ix, char **json_out, char digest_out[65]);

/* Exact CPU kernel, exposed for the qualification oracle and benchmarks.
 * Accumulation is double; stored vectors are float32. */
int  elpis_vector_score_block(const uint8_t *records, uint64_t count, uint32_t dimensions,
                              const float *query, uint32_t metric, double *scores_out);

#ifdef __cplusplus
}
#endif
#endif
