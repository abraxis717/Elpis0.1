/* context_requirement_set.c — Requirement set identity and validation.
 *
 * Identity domain: "elpis.semantic.context_requirement_set.v1"
 */
#include "elpis_semantic/context_requirement_set.h"
#include "elpis_semantic/identity.h"
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

static const char DOMAIN[] = "elpis.semantic.context_requirement_set.v1";

void elpis_context_requirement_set_init(
    elpis_semantic_context_requirement_set_v1 *set) {
    memset(set, 0, sizeof(*set));
    set->abi_version = CONTEXT_REQUIREMENT_SET_ABI_VERSION;
}

int elpis_context_requirement_set_canonicalize(
    elpis_semantic_context_requirement_set_v1 *set) {
    if (!set) return SEMANTIC_E_INVAL;
    /* Sort digests ascending using insertion sort */
    for (uint32_t i = 1; i < set->requirement_count; i++) {
        hacf_digest key = set->requirement_digests[i];
        uint32_t j = i;
        while (j > 0 && memcmp(key.bytes, set->requirement_digests[j - 1].bytes, HACF_DIGEST_BYTES) < 0) {
            set->requirement_digests[j] = set->requirement_digests[j - 1];
            j--;
        }
        set->requirement_digests[j] = key;
    }
    return SEMANTIC_OK;
}

int elpis_context_requirement_set_add(
    elpis_semantic_context_requirement_set_v1 *set,
    const hacf_digest *requirement_digest) {
    if (!set || !requirement_digest) return SEMANTIC_E_INVAL;
    if (set->requirement_count >= CONTEXT_MAX_REQUIREMENTS) return SEMANTIC_E_INVAL;

    /* Check for duplicate */
    for (uint32_t i = 0; i < set->requirement_count; i++) {
        if (memcmp(set->requirement_digests[i].bytes, requirement_digest->bytes, HACF_DIGEST_BYTES) == 0) {
            return SEMANTIC_E_DUPLICATE;
        }
    }

    /* Insert in sorted order */
    uint32_t insert_pos = set->requirement_count;
    for (uint32_t i = 0; i < set->requirement_count; i++) {
        if (memcmp(requirement_digest->bytes, set->requirement_digests[i].bytes, HACF_DIGEST_BYTES) < 0) {
            insert_pos = i;
            break;
        }
    }
    /* Shift */
    for (uint32_t i = set->requirement_count; i > insert_pos; i--) {
        set->requirement_digests[i] = set->requirement_digests[i - 1];
    }
    set->requirement_digests[insert_pos] = *requirement_digest;
    set->requirement_count++;
    return SEMANTIC_OK;
}

int elpis_context_requirement_set_identity(
    const elpis_semantic_context_requirement_set_v1 *set, hacf_digest *out) {
    if (!set || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, DOMAIN);
    write_u32_be(&ctx, set->abi_version);
    write_digest(&ctx, &set->target_query_overlay_digest);
    write_digest(&ctx, &set->target_composed_view_digest);
    write_u32_be(&ctx, set->requirement_count);
    for (uint32_t i = 0; i < set->requirement_count; i++) {
        write_digest(&ctx, &set->requirement_digests[i]);
    }
    write_digest(&ctx, &set->requirement_set_policy_digest);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_context_requirement_set_validate(
    const elpis_semantic_context_requirement_set_v1 *set) {
    if (!set) return SET_INVALID_ABI;
    if (set->abi_version != CONTEXT_REQUIREMENT_SET_ABI_VERSION) return SET_INVALID_ABI;

    {
        static const uint8_t zero_buf[32];
        if (memcmp(set->reserved, zero_buf, sizeof(set->reserved)) != 0) return SET_INVALID_ABI;
    }

    if (set->requirement_count > CONTEXT_MAX_REQUIREMENTS) return SET_COUNT_EXCEEDED;
    if (set->requirement_count == 0) return SET_INVALID_TARGET;

    /* Check target digests non-zero */
    {
        static const uint8_t zero_digest[HACF_DIGEST_BYTES];
        if (memcmp(set->target_query_overlay_digest.bytes, zero_digest, HACF_DIGEST_BYTES) == 0) return SET_OVERLAY_MISMATCH;
        if (memcmp(set->target_composed_view_digest.bytes, zero_digest, HACF_DIGEST_BYTES) == 0) return SET_INVALID_TARGET;
    }

    /* Check digests sorted and no duplicates */
    for (uint32_t i = 1; i < set->requirement_count; i++) {
        int cmp = memcmp(set->requirement_digests[i].bytes,
                         set->requirement_digests[i - 1].bytes,
                         HACF_DIGEST_BYTES);
        if (cmp < 0) return SET_INVALID_POLICY; /* not sorted */
        if (cmp == 0) return SET_DUPLICATE_REQUIREMENT;
    }

    return SET_VALID;
}
