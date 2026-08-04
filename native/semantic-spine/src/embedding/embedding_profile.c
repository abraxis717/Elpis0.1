/* embedding_profile.c — Embedding profile identity and validation. */
#include "elpis_semantic/embedding_profile.h"
#include "elpis/sha256.h"
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>

/* ──────────────────────────────────────────────────────────────────── */
/* Helper: write domain tag                                              */
/* ──────────────────────────────────────────────────────────────────── */

static void write_domain_tag(elpis_sha256_ctx *ctx, const char *domain) {
    size_t len = strlen(domain);
    uint32_t be_len = htonl((uint32_t)len);
    elpis_sha256_update(ctx, &be_len, 4);
    elpis_sha256_update(ctx, domain, len);
}

static void write_u32_be(elpis_sha256_ctx *ctx, uint32_t val) {
    uint32_t be = htonl(val);
    elpis_sha256_update(ctx, &be, 4);
}

static void write_digest(elpis_sha256_ctx *ctx, const hacf_digest *d) {
    elpis_sha256_update(ctx, d->bytes, HACF_DIGEST_BYTES);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Profile identity                                                      */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_profile_identity(const elpis_semantic_embedding_profile_v1 *profile,
                                      hacf_digest *out) {
    if (!profile || !out) return -1;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.embedding_profile.v1");
    write_u32_be(&ctx, profile->abi_version);
    write_u32_be(&ctx, (uint32_t)profile->provider_kind);
    write_digest(&ctx, &profile->model_identity_digest);
    write_digest(&ctx, &profile->tokenizer_identity_digest);
    write_digest(&ctx, &profile->preprocessing_policy_digest);
    write_u32_be(&ctx, (uint32_t)profile->pooling_policy);
    write_digest(&ctx, &profile->pooling_policy_digest);
    write_u32_be(&ctx, (uint32_t)profile->normalization_policy);
    write_digest(&ctx, &profile->normalization_policy_digest);
    write_u32_be(&ctx, (uint32_t)profile->distance_metric);
    write_u32_be(&ctx, profile->dimensions);
    write_u32_be(&ctx, (uint32_t)profile->vector_dtype);
    write_digest(&ctx, &profile->truncation_policy_digest);
    write_u32_be(&ctx, profile->profile_flags);
    elpis_sha256_final(&ctx, out->bytes);
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Profile validation                                                    */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_semantic_embedding_profile_validate(const elpis_semantic_embedding_profile_v1 *profile) {
    if (!profile) return -1;
    if (profile->abi_version != EMBEDDING_PROFILE_ABI_VERSION) return -1;

    /* Provider kind must be known. */
    if (profile->provider_kind < 1 || profile->provider_kind > 4) return -1;

    /* Pooling policy must be known. */
    if (profile->pooling_policy < 1 || profile->pooling_policy > 6) return -1;

    /* Normalization policy must be known. */
    if (profile->normalization_policy < 1 || profile->normalization_policy > 3) return -1;

    /* Distance metric must be known. */
    if (profile->distance_metric < 1 || profile->distance_metric > 3) return -1;

    /* Dimensions must be in range. */
    if (profile->dimensions < 1 || profile->dimensions > EMBEDDING_DIMENSION_CEILING) return -1;

    /* Vector dtype must be float32 in P1. */
    if (profile->vector_dtype != EMBEDDING_DTYPE_FLOAT32) return -1;

    /* Flags within mask. */
    if (profile->profile_flags & ~EMBEDDING_PROFILE_FLAG_MASK) return -1;

    /* Reserved fields must be zero. */
    static const uint8_t zero_buf[64] = {0};
    if (memcmp(profile->reserved, zero_buf, sizeof(profile->reserved)) != 0) return -1;

    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Lifecycle                                                               */
/* ──────────────────────────────────────────────────────────────────── */

elpis_semantic_embedding_profile_v1 *elpis_embedding_profile_create(void) {
    elpis_semantic_embedding_profile_v1 *p = calloc(1, sizeof(*p));
    if (!p) return NULL;
    p->abi_version = EMBEDDING_PROFILE_ABI_VERSION;
    return p;
}

void elpis_embedding_profile_destroy(elpis_semantic_embedding_profile_v1 *profile) {
    free(profile);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Comparison                                                              */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_profile_cmp(const elpis_semantic_embedding_profile_v1 *a,
                                 const elpis_semantic_embedding_profile_v1 *b) {
    if (!a || !b) return -1;
    return memcmp(a->profile_identity.bytes, b->profile_identity.bytes, HACF_DIGEST_BYTES);
}

int elpis_embedding_profile_is_same(const elpis_semantic_embedding_profile_v1 *a,
                                     const elpis_semantic_embedding_profile_v1 *b) {
    if (!a || !b) return 0;
    return memcmp(a->profile_identity.bytes, b->profile_identity.bytes, HACF_DIGEST_BYTES) == 0;
}
