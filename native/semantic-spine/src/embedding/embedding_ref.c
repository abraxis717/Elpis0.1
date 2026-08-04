/* embedding_ref.c — Node-to-embedding reference identity. */
#include "elpis_semantic/embedding_ref.h"
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
/* Reference identity                                                    */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_ref_identity(const elpis_semantic_embedding_ref_v1 *ref,
                                  hacf_digest *out) {
    if (!ref || !out) return -1;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.embedding_ref.v1");
    write_u32_be(&ctx, ref->abi_version);
    write_digest(&ctx, &ref->semantic_node_digest);
    write_digest(&ctx, &ref->embedding_profile_digest);
    write_digest(&ctx, &ref->embedding_vector_digest);
    write_u32_be(&ctx, ref->reference_flags);
    write_digest(&ctx, &ref->provenance_digest);
    write_u32_be(&ctx, ref->authority);
    elpis_sha256_final(&ctx, out->bytes);
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Validation                                                              */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_ref_validate(const elpis_semantic_embedding_ref_v1 *ref) {
    if (!ref) return -1;
    if (ref->abi_version != EMBEDDING_REF_ABI_VERSION) return -1;
    /* Semantic node digest must be non-zero */
    static const uint8_t zero_digest[32] = {0};
    if (memcmp(&ref->semantic_node_digest, zero_digest, sizeof(hacf_digest)) == 0) return -1;
    /* Profile digest must be non-zero */
    if (memcmp(&ref->embedding_profile_digest, zero_digest, sizeof(hacf_digest)) == 0) return -1;
    /* Vector digest must be non-zero */
    if (memcmp(&ref->embedding_vector_digest, zero_digest, sizeof(hacf_digest)) == 0) return -1;
    if (ref->reference_flags & ~EMBEDDING_REF_FLAG_MASK) return -1;
    if (ref->authority > EMBEDDING_AUTH_SYSTEM) return -1;
    static const uint8_t zero_buf[64] = {0};
    if (memcmp(ref->reserved, zero_buf, sizeof(ref->reserved)) != 0) return -1;
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Lifecycle                                                               */
/* ──────────────────────────────────────────────────────────────────── */

elpis_semantic_embedding_ref_v1 *elpis_embedding_ref_create(void) {
    elpis_semantic_embedding_ref_v1 *r = calloc(1, sizeof(*r));
    if (!r) return NULL;
    r->abi_version = EMBEDDING_REF_ABI_VERSION;
    return r;
}

void elpis_embedding_ref_destroy(elpis_semantic_embedding_ref_v1 *ref) {
    free(ref);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Comparison                                                              */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_ref_cmp(const elpis_semantic_embedding_ref_v1 *a,
                             const elpis_semantic_embedding_ref_v1 *b) {
    if (!a || !b) return -1;
    int c = memcmp(a->semantic_node_digest.bytes, b->semantic_node_digest.bytes, HACF_DIGEST_BYTES);
    if (c != 0) return c;
    c = memcmp(a->embedding_profile_digest.bytes, b->embedding_profile_digest.bytes, HACF_DIGEST_BYTES);
    if (c != 0) return c;
    c = memcmp(a->provenance_digest.bytes, b->provenance_digest.bytes, HACF_DIGEST_BYTES);
    if (c != 0) return c;
    uint32_t be_a = htonl(a->authority);
    uint32_t be_b = htonl(b->authority);
    c = memcmp(&be_a, &be_b, 4);
    if (c != 0) return c;
    be_a = htonl(a->reference_flags);
    be_b = htonl(b->reference_flags);
    c = memcmp(&be_a, &be_b, 4);
    if (c != 0) return c;
    return memcmp(a->embedding_vector_digest.bytes, b->embedding_vector_digest.bytes, HACF_DIGEST_BYTES);
}

int elpis_embedding_ref_is_duplicate(const elpis_semantic_embedding_ref_v1 *a,
                                      const elpis_semantic_embedding_ref_v1 *b) {
    if (!a || !b) return 0;
    return memcmp(a->ref_identity.bytes, b->ref_identity.bytes, HACF_DIGEST_BYTES) == 0;
}

int elpis_embedding_ref_is_conflict(const elpis_semantic_embedding_ref_v1 *a,
                                     const elpis_semantic_embedding_ref_v1 *b) {
    if (!a || !b) return 0;
    /* Same node, profile, provenance, authority, flags */
    if (memcmp(a->semantic_node_digest.bytes, b->semantic_node_digest.bytes, HACF_DIGEST_BYTES) != 0) return 0;
    if (memcmp(a->embedding_profile_digest.bytes, b->embedding_profile_digest.bytes, HACF_DIGEST_BYTES) != 0) return 0;
    if (memcmp(a->provenance_digest.bytes, b->provenance_digest.bytes, HACF_DIGEST_BYTES) != 0) return 0;
    if (a->authority != b->authority) return 0;
    if (a->reference_flags != b->reference_flags) return 0;
    /* But different vector → conflict */
    if (memcmp(a->embedding_vector_digest.bytes, b->embedding_vector_digest.bytes, HACF_DIGEST_BYTES) != 0) {
        return 1;
    }
    return 0;
}
