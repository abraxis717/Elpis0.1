/* identity.c — Semantic identity computation and validation.
 *
 * All identity digests use SHA-256 with explicit domain tags.
 * Domain tag format: UTF-8 bytes of the domain string, preceded by
 * big-endian uint32_t length. This avoids ambiguity.
 *
 * Integer fields are always big-endian on the wire.
 */
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>

/* Zero-comparison buffers — must be large enough for any field compared.
 * Using "\0" with sizeof(field) overreads the 2-byte string literal. */
static const uint8_t ZERO_32[32] = {0};
static const uint8_t ZERO_48[48] = {0};
static const uint8_t ZERO_64[64] = {0};

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
/* Node identity                                                       */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_semantic_node_identity(const elpis_semantic_node_v1 *node, hacf_digest *out) {
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.node.v1");
    write_u32_be(&ctx, node->abi_version);
    write_u32_be(&ctx, node->node_type);
    write_u32_be(&ctx, node->semantic_flags);
    write_digest(&ctx, &node->payload_digest);
    elpis_sha256_final(&ctx, out->bytes);
    return 0;
}

int elpis_semantic_node_validate(const elpis_semantic_node_v1 *node) {
    if (!node) return SEMANTIC_E_INVAL;
    if (node->abi_version != SEMANTIC_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (!(node->node_type & SEMANTIC_NODE_NAMESPACE)) return SEMANTIC_E_NAMESPACE_COLLISION;
    if (node->semantic_flags & ~SEMANTIC_NODE_FLAG_MASK) return SEMANTIC_E_RESERVATION;
    if (memcmp(node->reserved, ZERO_48, sizeof(node->reserved)) != 0) return SEMANTIC_E_RESERVATION;
    return SEMANTIC_OK;
}

int elpis_semantic_node_cmp(const elpis_semantic_node_v1 *a, const elpis_semantic_node_v1 *b) {
    if (!a || !b) return -1;
    return memcmp(a->node_identity.bytes, b->node_identity.bytes, HACF_DIGEST_BYTES);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Participant sorting                                                 */
/* ──────────────────────────────────────────────────────────────────── */

static int participant_cmp(const void *pa, const void *pb) {
    const elpis_semantic_participant_descriptor *a = (const elpis_semantic_participant_descriptor *)pa;
    const elpis_semantic_participant_descriptor *b = (const elpis_semantic_participant_descriptor *)pb;
    uint32_t be_a_role = htonl(a->incidence_role);
    uint32_t be_b_role = htonl(b->incidence_role);
    int c = memcmp(&be_a_role, &be_b_role, 4);
    if (c != 0) return c;
    uint32_t be_a_ord = htonl(a->ordinal);
    uint32_t be_b_ord = htonl(b->ordinal);
    c = memcmp(&be_a_ord, &be_b_ord, 4);
    if (c != 0) return c;
    c = memcmp(a->node_identity.bytes, b->node_identity.bytes, HACF_DIGEST_BYTES);
    if (c != 0) return c;
    uint32_t be_a_flags = htonl(a->participant_flags);
    uint32_t be_b_flags = htonl(b->participant_flags);
    return memcmp(&be_a_flags, &be_b_flags, 4);
}

int elpis_semantic_canonicalize_participants(elpis_semantic_participant_descriptor *parts, uint32_t count) {
    if (!parts || count == 0) return SEMANTIC_OK;
    if (count > SEMANTIC_MAX_PARTICIPANTS) return SEMANTIC_E_INVAL;
    /* qsort is deterministic for our comparator — full key comparison, no tie-breaking by address. */
    qsort(parts, count, sizeof(elpis_semantic_participant_descriptor), participant_cmp);
    return SEMANTIC_OK;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Hyperedge identity                                                  */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_semantic_hyperedge_identity(const elpis_semantic_hyperedge_v1 *edge, hacf_digest *out) {
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.hyperedge.v1");
    write_u32_be(&ctx, edge->abi_version);
    write_u32_be(&ctx, edge->hyperedge_type);
    write_u32_be(&ctx, edge->semantic_flags);
    write_digest(&ctx, &edge->payload_digest);
    write_u32_be(&ctx, edge->participant_count);
    /* Participants are already canonicalized before identity computation. */
    for (uint32_t i = 0; i < edge->participant_count; i++) {
        const elpis_semantic_participant_descriptor *p = &edge->participants[i];
        write_digest(&ctx, &p->node_identity);
        write_u32_be(&ctx, p->incidence_role);
        write_u32_be(&ctx, p->ordinal);
        write_u32_be(&ctx, p->participant_flags);
    }
    elpis_sha256_final(&ctx, out->bytes);
    return 0;
}

int elpis_semantic_hyperedge_validate(const elpis_semantic_hyperedge_v1 *edge) {
    if (!edge) return SEMANTIC_E_INVAL;
    if (edge->abi_version != SEMANTIC_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (!(edge->hyperedge_type & SEMANTIC_HYPEREDGE_NAMESPACE)) return SEMANTIC_E_NAMESPACE_COLLISION;
    if (edge->semantic_flags & ~SEMANTIC_HYPEREDGE_FLAG_MASK) return SEMANTIC_E_RESERVATION;
    if (edge->participant_count > SEMANTIC_MAX_PARTICIPANTS) return SEMANTIC_E_INVAL;
    if (memcmp(edge->reserved, ZERO_64, sizeof(edge->reserved)) != 0) return SEMANTIC_E_RESERVATION;
    for (uint32_t i = 0; i < edge->participant_count; i++) {
        const elpis_semantic_participant_descriptor *p = &edge->participants[i];
        if (!(p->incidence_role & SEMANTIC_INCIDENCE_NAMESPACE)) return SEMANTIC_E_NAMESPACE_COLLISION;
        if (p->participant_flags & ~SEMANTIC_PARTICIPANT_FLAG_MASK) return SEMANTIC_E_RESERVATION;
        if (memcmp(p->reserved, ZERO_32, sizeof(p->reserved)) != 0) return SEMANTIC_E_RESERVATION;
    }
    return SEMANTIC_OK;
}

int elpis_semantic_hyperedge_cmp(const elpis_semantic_hyperedge_v1 *a, const elpis_semantic_hyperedge_v1 *b) {
    if (!a || !b) return -1;
    return memcmp(a->hyperedge_identity.bytes, b->hyperedge_identity.bytes, HACF_DIGEST_BYTES);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Assertion identity                                                  */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_semantic_assertion_identity(const elpis_semantic_assertion_v1 *assertion, hacf_digest *out) {
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.assertion.v1");
    write_u32_be(&ctx, assertion->abi_version);
    write_u32_be(&ctx, assertion->asserted_object_kind);
    write_digest(&ctx, &assertion->asserted_object_digest);
    write_digest(&ctx, &assertion->provenance_digest);
    write_u32_be(&ctx, assertion->authority);
    write_u32_be(&ctx, assertion->assertion_flags);
    elpis_sha256_final(&ctx, out->bytes);
    return 0;
}

int elpis_semantic_assertion_validate(const elpis_semantic_assertion_v1 *assertion) {
    if (!assertion) return SEMANTIC_E_INVAL;
    if (assertion->abi_version != SEMANTIC_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (assertion->asserted_object_kind != SEMANTIC_OBJECT_KIND_NODE &&
        assertion->asserted_object_kind != SEMANTIC_OBJECT_KIND_HYPEREDGE) return SEMANTIC_E_INVAL;
    if (assertion->authority > 3) return SEMANTIC_E_AUTHORITY;
    if (assertion->assertion_flags & ~SEMANTIC_ASSERTION_FLAG_MASK) return SEMANTIC_E_RESERVATION;
    if (memcmp(assertion->reserved, ZERO_64, sizeof(assertion->reserved)) != 0) return SEMANTIC_E_RESERVATION;
    return SEMANTIC_OK;
}

int elpis_semantic_assertion_cmp(const elpis_semantic_assertion_v1 *a, const elpis_semantic_assertion_v1 *b) {
    if (!a || !b) return -1;
    int c = memcmp(a->asserted_object_digest.bytes, b->asserted_object_digest.bytes, HACF_DIGEST_BYTES);
    if (c != 0) return c;
    c = memcmp(a->provenance_digest.bytes, b->provenance_digest.bytes, HACF_DIGEST_BYTES);
    if (c != 0) return c;
    uint32_t be_a = htonl(a->authority);
    uint32_t be_b = htonl(b->authority);
    c = memcmp(&be_a, &be_b, 4);
    if (c != 0) return c;
    uint32_t be_af = htonl(a->assertion_flags);
    uint32_t be_bf = htonl(b->assertion_flags);
    return memcmp(&be_af, &be_bf, 4);
}

int elpis_semantic_assertion_is_duplicate(const elpis_semantic_assertion_v1 *a, const elpis_semantic_assertion_v1 *b) {
    if (!a || !b) return 0;
    return memcmp(a->assertion_identity.bytes, b->assertion_identity.bytes, HACF_DIGEST_BYTES) == 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Incidence identity                                                  */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_semantic_incidence_identity(const elpis_semantic_incidence_v1 *incidence, hacf_digest *out) {
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.incidence.v1");
    write_u32_be(&ctx, incidence->abi_version);
    write_digest(&ctx, &incidence->hyperedge_digest);
    write_digest(&ctx, &incidence->node_digest);
    write_u32_be(&ctx, incidence->incidence_role);
    write_u32_be(&ctx, incidence->ordinal);
    write_u32_be(&ctx, incidence->participant_flags);
    elpis_sha256_final(&ctx, out->bytes);
    return 0;
}

int elpis_semantic_incidence_validate(const elpis_semantic_incidence_v1 *incidence) {
    if (!incidence) return SEMANTIC_E_INVAL;
    if (incidence->abi_version != SEMANTIC_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (!(incidence->incidence_role & SEMANTIC_INCIDENCE_NAMESPACE)) return SEMANTIC_E_NAMESPACE_COLLISION;
    if (incidence->participant_flags & ~SEMANTIC_INCIDENCE_FLAG_MASK) return SEMANTIC_E_RESERVATION;
    if (memcmp(incidence->reserved, ZERO_32, sizeof(incidence->reserved)) != 0) return SEMANTIC_E_RESERVATION;
    return SEMANTIC_OK;
}

int elpis_semantic_incidence_cmp(const elpis_semantic_incidence_v1 *a, const elpis_semantic_incidence_v1 *b) {
    if (!a || !b) return -1;
    int c = memcmp(a->hyperedge_digest.bytes, b->hyperedge_digest.bytes, HACF_DIGEST_BYTES);
    if (c != 0) return c;
    uint32_t be_a = htonl(a->incidence_role);
    uint32_t be_b = htonl(b->incidence_role);
    c = memcmp(&be_a, &be_b, 4);
    if (c != 0) return c;
    be_a = htonl(a->ordinal);
    be_b = htonl(b->ordinal);
    c = memcmp(&be_a, &be_b, 4);
    if (c != 0) return c;
    c = memcmp(a->node_digest.bytes, b->node_digest.bytes, HACF_DIGEST_BYTES);
    if (c != 0) return c;
    be_a = htonl(a->participant_flags);
    be_b = htonl(b->participant_flags);
    return memcmp(&be_a, &be_b, 4);
}
