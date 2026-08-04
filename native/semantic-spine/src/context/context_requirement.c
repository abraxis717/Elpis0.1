/* context_requirement.c — Context requirement identity and validation.
 *
 * Implements the public ABI for elpis_semantic_context_requirement_v1.
 * Identity domain: "elpis.semantic.context_requirement.v1"
 */
#include "elpis_semantic/context_requirement.h"
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

static const char DOMAIN[] = "elpis.semantic.context_requirement.v1";

void elpis_context_requirement_init(elpis_semantic_context_requirement_v1 *req) {
    memset(req, 0, sizeof(*req));
    req->abi_version = CONTEXT_REQUIREMENT_ABI_VERSION;
}

int elpis_context_requirement_identity(
    const elpis_semantic_context_requirement_v1 *req, hacf_digest *out) {
    if (!req || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, DOMAIN);
    write_u32_be(&ctx, req->abi_version);
    write_u32_be(&ctx, (uint32_t)req->requirement_type);
    write_u32_be(&ctx, (uint32_t)req->requirement_level);
    write_u32_be(&ctx, (uint32_t)req->target_object_kind);
    write_digest(&ctx, &req->target_object_digest);
    write_digest(&ctx, &req->requirement_policy_digest);
    write_u32_be(&ctx, req->minimum_authority);
    write_u32_be(&ctx, req->requirement_flags);
    write_u32_be(&ctx, req->extension_size);
    elpis_sha256_update(&ctx, req->extension_bytes, req->extension_size);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_context_requirement_validate(
    const elpis_semantic_context_requirement_v1 *req) {
    if (!req) return SEMANTIC_E_INVAL;
    if (req->abi_version != CONTEXT_REQUIREMENT_ABI_VERSION) return SEMANTIC_E_INVAL;

    /* Validate requirement type */
    if ((uint32_t)req->requirement_type < TYPE_OBJECT_PRESENT ||
        (uint32_t)req->requirement_type > TYPE_OPAQUE_APPLICATION) {
        return SEMANTIC_E_INVAL;
    }

    /* Validate requirement level */
    if ((uint32_t)req->requirement_level < MANDATORY ||
        (uint32_t)req->requirement_level > DIAGNOSTIC) {
        return SEMANTIC_E_INVAL;
    }

    /* Validate target object kind */
    if ((uint32_t)req->target_object_kind > KIND_EMBEDDING_VECTOR) {
        return SEMANTIC_E_INVAL;
    }

    /* Validate extension size */
    if (req->extension_size > CONTEXT_MAX_EXTENSION_BYTES) {
        return SEMANTIC_E_INVAL;
    }

    /* Validate reserved fields are zero */
    {
        static const uint8_t zero_buf[32];
        if (memcmp(req->reserved, zero_buf, sizeof(req->reserved)) != 0) {
            return SEMANTIC_E_RESERVATION;
        }
    }

    return SEMANTIC_OK;
}

int elpis_context_requirement_is_duplicate(
    const elpis_semantic_context_requirement_v1 *a,
    const elpis_semantic_context_requirement_v1 *b) {
    if (!a || !b) return SEMANTIC_E_INVAL;
    return (memcmp(a->requirement_identity.bytes,
                   b->requirement_identity.bytes,
                   HACF_DIGEST_BYTES) == 0) ? 1 : 0;
}
