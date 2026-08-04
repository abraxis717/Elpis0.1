/* embedding_collection.c — Embedding-reference collections.
 *
 * Collections are immutable. Adding a reference creates a new collection.
 * Canonical order: profiles by digest, vectors by digest, references by key.
 */
#include "elpis_semantic/embedding_collection.h"
#include "elpis/sha256.h"
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>

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
/* Collection identity                                                   */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_collection_finalize(elpis_semantic_embedding_collection_v1 *col,
                                         hacf_digest *out) {
    if (!col || !out) return -1;
    if (col->profile_count > EMBEDDING_MAX_PROFILES) return -1;
    if (col->vector_count > EMBEDDING_MAX_VECTORS) return -1;
    if (col->reference_count > EMBEDDING_MAX_REFERENCES) return -1;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.embedding_collection.v1");
    write_u32_be(&ctx, col->abi_version);
    write_u32_be(&ctx, (uint32_t)col->target_kind);
    write_digest(&ctx, &col->target_digest);
    write_u32_be(&ctx, col->profile_count);
    for (uint32_t i = 0; i < col->profile_count; i++) {
        write_digest(&ctx, &col->profile_digests[i]);
    }
    write_u32_be(&ctx, col->vector_count);
    for (uint32_t i = 0; i < col->vector_count; i++) {
        write_digest(&ctx, &col->vector_digests[i]);
    }
    write_u32_be(&ctx, col->reference_count);
    for (uint32_t i = 0; i < col->reference_count; i++) {
        write_digest(&ctx, &col->reference_digests[i]);
    }
    write_digest(&ctx, &col->collection_policy_digest);
    elpis_sha256_final(&ctx, out->bytes);

    memcpy(&col->collection_identity, out, sizeof(hacf_digest));
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Add operations (canonical insert with dedup)                          */
/* ──────────────────────────────────────────────────────────────────── */

/* Insert a digest into a sorted array, maintaining order. Returns 1 if new, 0 if duplicate. */
static int insert_sorted_digest(hacf_digest *array, uint32_t *count, uint32_t max,
                                 const hacf_digest *digest) {
    if (*count >= max) return -1;
    /* Check for existing */
    for (uint32_t i = 0; i < *count; i++) {
        if (memcmp(&array[i], digest, sizeof(hacf_digest)) == 0) return 0;
    }
    /* Insert in sorted position */
    uint32_t pos = *count;
    for (uint32_t i = 0; i < *count; i++) {
        if (memcmp(&array[i], digest, sizeof(hacf_digest)) > 0) {
            pos = i;
            break;
        }
    }
    /* Shift right */
    if (pos < *count) {
        memmove(&array[pos + 1], &array[pos], (*count - pos) * sizeof(hacf_digest));
    }
    memcpy(&array[pos], digest, sizeof(hacf_digest));
    (*count)++;
    return 1;
}

int elpis_embedding_collection_add_profile(elpis_semantic_embedding_collection_v1 *col,
                                            const hacf_digest *profile_digest) {
    if (!col || !profile_digest) return -1;
    return insert_sorted_digest(col->profile_digests, &col->profile_count,
                                 EMBEDDING_MAX_PROFILES, profile_digest);
}

int elpis_embedding_collection_add_vector(elpis_semantic_embedding_collection_v1 *col,
                                           const hacf_digest *vector_digest) {
    if (!col || !vector_digest) return -1;
    return insert_sorted_digest(col->vector_digests, &col->vector_count,
                                 EMBEDDING_MAX_VECTORS, vector_digest);
}

int elpis_embedding_collection_add_reference(elpis_semantic_embedding_collection_v1 *col,
                                              const hacf_digest *reference_digest) {
    if (!col || !reference_digest) return -1;
    return insert_sorted_digest(col->reference_digests, &col->reference_count,
                                 EMBEDDING_MAX_REFERENCES, reference_digest);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Validation                                                              */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_collection_validate(const elpis_semantic_embedding_collection_v1 *col) {
    if (!col) return -1;
    if (col->abi_version != EMBEDDING_COLLECTION_ABI_VERSION) return -1;
    if (col->target_kind < 1 || col->target_kind > 2) return -1;
    /* Target digest must be non-zero */
    static const uint8_t zero_digest[32] = {0};
    if (memcmp(&col->target_digest, zero_digest, sizeof(hacf_digest)) == 0) return -1;
    if (col->profile_count > EMBEDDING_MAX_PROFILES) return -1;
    if (col->vector_count > EMBEDDING_MAX_VECTORS) return -1;
    if (col->reference_count > EMBEDDING_MAX_REFERENCES) return -1;
    static const uint8_t zero_buf[64] = {0};
    if (memcmp(col->reserved, zero_buf, sizeof(col->reserved)) != 0) return -1;

    /* Verify sorted order of digests */
    for (uint32_t i = 1; i < col->profile_count; i++) {
        if (memcmp(&col->profile_digests[i - 1], &col->profile_digests[i], sizeof(hacf_digest)) > 0)
            return -1;
    }
    for (uint32_t i = 1; i < col->vector_count; i++) {
        if (memcmp(&col->vector_digests[i - 1], &col->vector_digests[i], sizeof(hacf_digest)) > 0)
            return -1;
    }
    for (uint32_t i = 1; i < col->reference_count; i++) {
        if (memcmp(&col->reference_digests[i - 1], &col->reference_digests[i], sizeof(hacf_digest)) > 0)
            return -1;
    }
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Lifecycle                                                               */
/* ──────────────────────────────────────────────────────────────────── */

elpis_semantic_embedding_collection_v1 *elpis_embedding_collection_create(void) {
    elpis_semantic_embedding_collection_v1 *c = calloc(1, sizeof(*c));
    if (!c) return NULL;
    c->abi_version = EMBEDDING_COLLECTION_ABI_VERSION;
    return c;
}

void elpis_embedding_collection_destroy(elpis_semantic_embedding_collection_v1 *col) {
    free(col);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Comparison                                                              */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_collection_cmp(const elpis_semantic_embedding_collection_v1 *a,
                                    const elpis_semantic_embedding_collection_v1 *b) {
    if (!a || !b) return -1;
    return memcmp(a->collection_identity.bytes, b->collection_identity.bytes, HACF_DIGEST_BYTES);
}
