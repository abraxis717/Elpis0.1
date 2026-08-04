/* elpis/embedding_provider.h - embedding provider ABI (Gate R2).
 *
 * Retrieval is not coupled to one model. A provider is identified by a profile
 * whose digest is bound into every shard it produces; a shard built under one
 * profile can never be searched with a query embedded under another.
 *
 * Two providers exist in R2:
 *   fixture  - deterministic, SHA-256 derived, no model files, tests only
 *   external - accepts precomputed vectors produced outside HACF
 *
 * Neither executes Python, downloads a model, or opens a socket. */
#ifndef ELPIS_EMBEDDING_PROVIDER_H
#define ELPIS_EMBEDDING_PROVIDER_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ELPIS_EMBEDDING_ABI_VERSION 1u
#define ELPIS_EMBEDDING_DIM         384u

/* Stored element type. Only float32 exists in R2; the field is present so a
 * quantized profile is a new declared type rather than a silent change. */
enum { ELPIS_ELEM_F32 = 1u };

/* Normalization policy applied by the provider to every emitted vector. */
enum { ELPIS_NORM_NONE = 0u, ELPIS_NORM_L2 = 1u };

/* Similarity metric. With ELPIS_NORM_L2 both are numerically identical; the
 * distinction is retained so the shard header states what was intended. */
enum { ELPIS_METRIC_DOT = 1u, ELPIS_METRIC_COSINE = 2u };

typedef struct elpis_embedding_profile {
    uint32_t abi_version;
    uint32_t dimensions;
    uint32_t element_type;
    uint32_t normalization;
    uint32_t metric;
    uint32_t max_input_bytes;
    uint32_t batch_limit;
    uint32_t reserved;
    char     name[64];              /* "fixture-sha256-v2" */
    char     backend[32];           /* "cpu-fixture" | "external" */
    char     device[64];            /* "cpu" | descriptor supplied by the producer */
    char     model_digest[65];      /* hex; all-zero hex for the fixture provider */
    char     tokenizer_digest[65];
} elpis_embedding_profile;

/* Canonical profile digest. Deterministic across hosts: fixed field order,
 * little-endian integers, no padding bytes, no locale. */
int  elpis_embedding_profile_digest(const elpis_embedding_profile *p, char out[65]);
int  elpis_embedding_profile_validate(const elpis_embedding_profile *p);
int  elpis_embedding_profile_equal(const elpis_embedding_profile *a,
                                   const elpis_embedding_profile *b);

typedef struct elpis_embedder elpis_embedder;

/* Deterministic fixture provider. Not semantically meaningful; it exists to
 * qualify storage, scoring, ranking, corruption handling and FMS integration. */
int  elpis_embedder_fixture_create(uint32_t normalization, elpis_embedder **out);

/* External provider: validates precomputed vectors, produces none itself. */
int  elpis_embedder_external_create(const elpis_embedding_profile *profile,
                                    elpis_embedder **out);

void elpis_embedder_destroy(elpis_embedder *e);
int  elpis_embedder_profile(const elpis_embedder *e, elpis_embedding_profile *out);

/* Fixture path: derive a vector from arbitrary bytes. Fails on an external
 * provider, which cannot synthesise vectors. */
int  elpis_embedder_embed(elpis_embedder *e, const void *bytes, size_t len,
                          float *out, uint32_t out_dim);

/* External path: admit a caller-supplied vector after validating dimension,
 * finiteness, normalization policy and profile digest. Fails on the fixture
 * provider. profile_digest may be NULL to skip the binding check only when the
 * caller has already verified it. */
int  elpis_embedder_accept(elpis_embedder *e, const float *in, uint32_t in_dim,
                           const char *profile_digest, float *out, uint32_t out_dim);

const char *elpis_embedder_error(const elpis_embedder *e);

/* Shared helpers, also used by the shard reader and the search kernel. */
int  elpis_vector_all_finite(const float *v, uint32_t dim);
int  elpis_vector_l2_normalize(float *v, uint32_t dim);   /* -1 on zero norm */
double elpis_vector_l2_norm(const float *v, uint32_t dim);

#ifdef __cplusplus
}
#endif
#endif
