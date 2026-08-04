/* elpis/vector_result.h - dense retrieval result ABI (Gate R2). */
#ifndef ELPIS_VECTOR_RESULT_H
#define ELPIS_VECTOR_RESULT_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Vector-layer status. Distinct from fms_status: an FMS code is never returned
 * to a vector caller, it is preserved in elpis_vec_error.cause. */
typedef enum {
    ELPIS_VEC_OK           =  0,
    ELPIS_VEC_E_INVAL      = -1,   /* malformed argument */
    ELPIS_VEC_E_QUERY      = -2,   /* query vector rejected (dimension, finiteness, zero norm) */
    ELPIS_VEC_E_PROFILE    = -3,   /* embedding-profile or corpus-manifest binding mismatch */
    ELPIS_VEC_E_FORMAT     = -4,   /* shard failed a structural check */
    ELPIS_VEC_E_INTEGRITY  = -5,   /* digest/corruption; cause carries FMS_E_DIGEST when it came from FMS */
    ELPIS_VEC_E_RESIDENCY  = -6,   /* shard could not be made WARM-resident */
    ELPIS_VEC_E_DUPLICATE  = -7,   /* duplicate chunk digest or shard already admitted */
    ELPIS_VEC_E_NOTFOUND   = -8,
    ELPIS_VEC_E_LIMIT      = -9,   /* index capacity */
    ELPIS_VEC_E_INTERNAL   = -10
} elpis_vec_status;

/* Structured error. cause holds the underlying fms_status (negative) when the
 * failure originated in FMS, otherwise 0. An integrity failure is never
 * downgraded to "no results", "not found", "out of memory" or "try again". */
typedef struct elpis_vec_error {
    int  status;        /* elpis_vec_status */
    int  cause;         /* fms_status, or 0 */
    char detail[192];
} elpis_vec_error;

const char *elpis_vec_strerror(int status);

/* Canonical score key for the normalized indexed domain [-1,1]:
 * round(score * 1e12), half away from zero. Ranking and every cross-host digest
 * bind this integer, never a host double. Finite direct-call overshoot is
 * clamped; non-finite direct input maps to INT64_MIN. Indexed search rejects
 * non-finite or materially out-of-domain scores before conversion. */
int64_t elpis_vector_score_key(double score);

#define ELPIS_VEC_SCORE_SCALE 1000000000000LL

typedef struct elpis_vector_hit {
    char     chunk_digest[65];
    char     doc_digest[65];
    char     shard_digest[65];
    char     embedding_profile_digest[65];
    char     ns[96];
    char     authority[32];
    double   score;            /* host double, diagnostic only */
    int64_t  score_key;        /* canonical, identity-bearing */
    uint32_t rank;             /* 0-based, assigned after deterministic ordering */
} elpis_vector_hit;

/* Deterministic ordering: higher score_key first, then lexicographically
 * smaller chunk digest. Returns <0, 0, >0. */
int elpis_vector_hit_compare(const elpis_vector_hit *a, const elpis_vector_hit *b);

/* Digest over the ordered result list. Scores enter as canonical score_key
 * integers, never as raw host double bytes and never as formatted text. */
int elpis_vector_result_digest(const elpis_vector_hit *hits, uint32_t n, char out[65]);

#ifdef __cplusplus
}
#endif
#endif
