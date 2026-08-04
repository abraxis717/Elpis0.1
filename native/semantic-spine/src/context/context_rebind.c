/* context_rebind.c — Requirement-set rebind for P5 context re-evaluation. */
#include "elpis_semantic/context_rebind.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdbool.h>
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

static const char *REBIND_DOMAIN = "elpis.semantic.context_rebind.v1";

void elpis_context_rebind_init(elpis_semantic_context_rebind_v1 *receipt) {
    memset(receipt, 0, sizeof(*receipt));
    receipt->abi_version = CONTEXT_REBIND_ABI_VERSION;
}

int elpis_context_rebind_requirement_set(
    const elpis_semantic_context_requirement_set_v1 *original_set,
    const hacf_digest *new_query_overlay_digest,
    const hacf_digest *new_typed_evidence_view_digest,
    elpis_semantic_context_rebind_v1 *receipt)
{
    if (!original_set || !new_query_overlay_digest ||
        !new_typed_evidence_view_digest || !receipt) {
        return SEMANTIC_E_INVAL;
    }

    int rc = elpis_context_requirement_set_validate(original_set);
    if (rc != SET_VALID) {
        receipt->disposition = REQUIREMENT_SET_REBIND_BLOCKED_BY_IDENTITY;
        return SEMANTIC_E_INVAL;
    }

    elpis_context_rebind_init(receipt);

    memcpy(&receipt->original_requirement_set_digest,
           &original_set->requirement_set_identity, HACF_DIGEST_BYTES);
    memcpy(&receipt->original_query_overlay_digest,
           &original_set->target_query_overlay_digest, HACF_DIGEST_BYTES);
    memcpy(&receipt->original_composed_view_digest,
           &original_set->target_composed_view_digest, HACF_DIGEST_BYTES);
    memcpy(&receipt->new_query_overlay_digest, new_query_overlay_digest,
           HACF_DIGEST_BYTES);
    memcpy(&receipt->new_typed_evidence_view_digest,
           new_typed_evidence_view_digest, HACF_DIGEST_BYTES);

    receipt->original_requirement_count = original_set->requirement_count;
    receipt->rebound_requirement_count = original_set->requirement_count;
    for (uint32_t i = 0; i < original_set->requirement_count; i++) {
        memcpy(&receipt->ordered_original_requirement_digests[i],
               &original_set->requirement_digests[i], HACF_DIGEST_BYTES);
        memcpy(&receipt->ordered_rebound_requirement_digests[i],
               &original_set->requirement_digests[i], HACF_DIGEST_BYTES);
    }
    memcpy(&receipt->original_requirement_set_policy_digest,
           &original_set->requirement_set_policy_digest, HACF_DIGEST_BYTES);

    elpis_semantic_context_requirement_set_v1 rebound;
    elpis_context_requirement_set_init(&rebound);
    memcpy(&rebound.target_query_overlay_digest, new_query_overlay_digest,
           HACF_DIGEST_BYTES);
    memcpy(&rebound.target_composed_view_digest, new_typed_evidence_view_digest,
           HACF_DIGEST_BYTES);
    rebound.requirement_count = original_set->requirement_count;
    for (uint32_t i = 0; i < original_set->requirement_count; i++) {
        memcpy(&rebound.requirement_digests[i],
               &original_set->requirement_digests[i], HACF_DIGEST_BYTES);
    }
    memcpy(&rebound.requirement_set_policy_digest,
           &original_set->requirement_set_policy_digest, HACF_DIGEST_BYTES);
    elpis_context_requirement_set_identity(&rebound,
                                           &receipt->rebound_requirement_set_digest);
    memset(&receipt->rebind_policy_digest, 0, HACF_DIGEST_BYTES);
    receipt->disposition = REQUIREMENT_SET_REBOUND;
    elpis_context_rebind_identity(receipt, &receipt->rebind_receipt_digest);
    return SEMANTIC_OK;
}

int elpis_context_rebind_identity(
    const elpis_semantic_context_rebind_v1 *receipt, hacf_digest *out)
{
    if (!receipt || !out || receipt->abi_version != CONTEXT_REBIND_ABI_VERSION)
        return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, REBIND_DOMAIN);
    uint32_t ver = receipt->abi_version;
    write_u32_be(&ctx, ver);
    elpis_sha256_update(&ctx, receipt->original_requirement_set_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->original_query_overlay_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->original_composed_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->new_query_overlay_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->new_typed_evidence_view_digest.bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, receipt->original_requirement_count);
    for (uint32_t i = 0; i < receipt->original_requirement_count; i++) {
        elpis_sha256_update(&ctx, receipt->ordered_original_requirement_digests[i].bytes, HACF_DIGEST_BYTES);
    }
    write_u32_be(&ctx, receipt->rebound_requirement_count);
    for (uint32_t i = 0; i < receipt->rebound_requirement_count; i++) {
        elpis_sha256_update(&ctx, receipt->ordered_rebound_requirement_digests[i].bytes, HACF_DIGEST_BYTES);
    }
    elpis_sha256_update(&ctx, receipt->original_requirement_set_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->rebound_requirement_set_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->rebind_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_context_rebind_validate(const elpis_semantic_context_rebind_v1 *receipt) {
    if (!receipt) return SEMANTIC_E_INVAL;
    if (receipt->abi_version != CONTEXT_REBIND_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (receipt->original_requirement_count != receipt->rebound_requirement_count)
        return SEMANTIC_E_INVAL;
    if (receipt->original_requirement_count > CONTEXT_MAX_REQUIREMENTS)
        return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(receipt->reserved); i++) {
        if (receipt->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    if (receipt->disposition > 3) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_context_rebind_construct_set(
    const elpis_semantic_context_rebind_v1 *receipt,
    elpis_semantic_context_requirement_set_v1 *rebound_set)
{
    if (!receipt || !rebound_set) return SEMANTIC_E_INVAL;
    if (receipt->disposition != REQUIREMENT_SET_REBOUND) return SEMANTIC_E_INVAL;
    elpis_context_requirement_set_init(rebound_set);
    memcpy(&rebound_set->target_query_overlay_digest,
           &receipt->new_query_overlay_digest, HACF_DIGEST_BYTES);
    memcpy(&rebound_set->target_composed_view_digest,
           &receipt->new_typed_evidence_view_digest, HACF_DIGEST_BYTES);
    rebound_set->requirement_count = receipt->rebound_requirement_count;
    for (uint32_t i = 0; i < receipt->rebound_requirement_count; i++) {
        memcpy(&rebound_set->requirement_digests[i],
               &receipt->ordered_rebound_requirement_digests[i], HACF_DIGEST_BYTES);
    }
    memcpy(&rebound_set->requirement_set_policy_digest,
           &receipt->original_requirement_set_policy_digest, HACF_DIGEST_BYTES);
    elpis_context_requirement_set_identity(rebound_set,
                                           &rebound_set->requirement_set_identity);
    return SEMANTIC_OK;
}

int elpis_context_rebind_verify_semantic_equivalence(
    const elpis_semantic_context_rebind_v1 *receipt)
{
    if (!receipt) return SEMANTIC_E_INVAL;
    if (receipt->original_requirement_count != receipt->rebound_requirement_count)
        return SEMANTIC_E_INVAL;
    for (uint32_t i = 0; i < receipt->original_requirement_count; i++) {
        if (memcmp(&receipt->ordered_original_requirement_digests[i],
                   &receipt->ordered_rebound_requirement_digests[i],
                   HACF_DIGEST_BYTES) != 0) {
            return SEMANTIC_E_INVAL;
        }
    }
    return SEMANTIC_OK;
}

/* ── Persistence ── */
extern int p5_simple_write(const char *path, const uint8_t *data, size_t sz);

int elpis_write_context_rebind(const char *path,
                                const elpis_semantic_context_rebind_v1 *receipt) {
    if (!path || !receipt) return SEMANTIC_E_INVAL;
    return p5_simple_write(path, (const uint8_t *)receipt, sizeof(*receipt));
}

int elpis_read_context_rebind(const char *path,
                               elpis_semantic_context_rebind_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    if (sz != (long)sizeof(*out)) { fclose(f); return SEMANTIC_E_IO; }
    fseek(f, 0, SEEK_SET);
    size_t rd = fread(out, 1, sizeof(*out), f);
    fclose(f);
    if (rd != sizeof(*out)) return SEMANTIC_E_IO;
    int rc = elpis_context_rebind_validate(out);
    if (rc != SEMANTIC_OK) return rc;
    hacf_digest computed;
    elpis_context_rebind_identity(out, &computed);
    if (memcmp(&computed, &out->rebind_receipt_digest, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_E_DIGEST;
    return SEMANTIC_OK;
}
