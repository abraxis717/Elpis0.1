/* retrieval_requirement.c — Retrieval requirement identity and validation.
 *
 * Identity domain: "elpis.semantic.retrieval_requirement.v1"
 */
#include "elpis_semantic/retrieval_requirement.h"
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

static const char DOMAIN[] = "elpis.semantic.retrieval_requirement.v1";

void elpis_retrieval_requirement_init(
    elpis_semantic_retrieval_requirement_v1 *req) {
    memset(req, 0, sizeof(*req));
    req->abi_version = RETRIEVAL_REQUIREMENT_ABI_VERSION;
}

int elpis_retrieval_requirement_identity(
    const elpis_semantic_retrieval_requirement_v1 *req, hacf_digest *out) {
    if (!req || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, DOMAIN);
    write_u32_be(&ctx, req->abi_version);
    write_digest(&ctx, &req->originating_requirement_digest);
    write_u32_be(&ctx, req->deficit_reason);
    write_u32_be(&ctx, req->retrieval_purpose);
    write_u32_be(&ctx, req->target_object_kind);
    write_digest(&ctx, &req->target_object_digest);
    write_u32_be(&ctx, req->requested_semantic_type);
    write_digest(&ctx, &req->requested_namespace_digest);
    write_u32_be(&ctx, req->requested_min_authority);
    write_digest(&ctx, &req->requested_embedding_profile_digest);
    write_u32_be(&ctx, req->query_source_kind);
    write_digest(&ctx, &req->query_source_digest);
    write_u32_be(&ctx, req->requested_result_limit);
    write_u32_be(&ctx, req->retrieval_flags);
    write_u32_be(&ctx, req->requirement_priority_key);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_retrieval_requirement_validate(
    const elpis_semantic_retrieval_requirement_v1 *req) {
    if (!req) return SEMANTIC_E_INVAL;
    if (req->abi_version != RETRIEVAL_REQUIREMENT_ABI_VERSION) return SEMANTIC_E_INVAL;

    /* Originating requirement digest must be non-zero */
    {
        static const uint8_t zero_buf[HACF_DIGEST_BYTES];
        if (memcmp(req->originating_requirement_digest.bytes, zero_buf, HACF_DIGEST_BYTES) == 0) {
            return SEMANTIC_E_INVAL;
        }
    }

    /* Result limit must be > 0 */
    if (req->requested_result_limit == 0) return SEMANTIC_E_INVAL;

    /* Valid retrieval purpose */
    if (req->retrieval_purpose < RETRIEVAL_PURPOSE_OBJECT_LOOKUP ||
        req->retrieval_purpose > RETRIEVAL_PURPOSE_CONFLICT_RESOLUTION) {
        return SEMANTIC_E_INVAL;
    }

    /* Valid query source kind */
    if (req->query_source_kind < SOURCE_OVERLAY ||
        req->query_source_kind > SOURCE_OPAQUE) {
        return SEMANTIC_E_INVAL;
    }

    /* Reserved must be zero */
    {
        static const uint8_t zero_buf[32];
        if (memcmp(req->reserved, zero_buf, sizeof(req->reserved)) != 0) {
            return SEMANTIC_E_RESERVATION;
        }
    }

    return SEMANTIC_OK;
}

int elpis_retrieval_requirement_is_duplicate(
    const elpis_semantic_retrieval_requirement_v1 *a,
    const elpis_semantic_retrieval_requirement_v1 *b) {
    if (!a || !b) return SEMANTIC_E_INVAL;
    return (memcmp(a->retrieval_identity.bytes,
                   b->retrieval_identity.bytes,
                   HACF_DIGEST_BYTES) == 0) ? 1 : 0;
}

int elpis_retrieval_requirement_cmp(
    const elpis_semantic_retrieval_requirement_v1 *a,
    const elpis_semantic_retrieval_requirement_v1 *b) {
    if (!a || !b) return -1;
    /* Higher priority first (descending), then digest ascending */
    int c = (int)b->requirement_priority_key - (int)a->requirement_priority_key;
    if (c != 0) return c;
    return memcmp(a->retrieval_identity.bytes, b->retrieval_identity.bytes, HACF_DIGEST_BYTES);
}

int elpis_retrieval_requirement_from_deficit(
    const elpis_semantic_context_requirement_v1 *requirement,
    const elpis_semantic_requirement_result_v1  *result,
    const hacf_digest                            *query_overlay_digest,
    elpis_semantic_retrieval_requirement_v1      *out) {
    if (!requirement || !result || !query_overlay_digest || !out) {
        return SEMANTIC_E_INVAL;
    }
    if (result->satisfaction_status != SAT_STATUS_UNSATISFIED) {
        return SEMANTIC_E_INVAL; /* Only produce retrieval for unsatisfied */
    }

    elpis_retrieval_requirement_init(out);

    /* Copy originating requirement digest */
    memcpy(out->originating_requirement_digest.bytes,
           requirement->requirement_identity.bytes, HACF_DIGEST_BYTES);

    out->deficit_reason = result->deficit_reason;

    /* Map deficit reason to retrieval purpose */
    switch (result->deficit_reason) {
        case DEF_OBJECT_ABSENT:
            out->retrieval_purpose = RETRIEVAL_PURPOSE_OBJECT_LOOKUP;
            break;
        case DEF_TYPE_COVERAGE_BELOW_MIN:
        case DEF_TYPE_COVERAGE_ABOVE_MAX:
            out->retrieval_purpose = RETRIEVAL_PURPOSE_TYPE_COVERAGE;
            break;
        case DEF_ASSERTION_COUNT_BELOW_MIN:
        case DEF_PROVENANCE_DIVERSITY_BELOW_MIN:
        case DEF_AUTHORITY_BELOW_MIN:
            out->retrieval_purpose = RETRIEVAL_PURPOSE_ASSERTION_SUPPORT;
            break;
        case DEF_EVIDENCE_RELATION_ABSENT:
        case DEF_EVIDENCE_COUNT_BELOW_MIN:
        case DEF_EVIDENCE_PROVENANCE_BELOW_MIN:
            out->retrieval_purpose = RETRIEVAL_PURPOSE_EVIDENCE_RELATION;
            break;
        case DEF_EXTERNAL_CONTEXT_REQUIRED:
            out->retrieval_purpose = RETRIEVAL_PURPOSE_EXTERNAL_CONTEXT;
            break;
        case DEF_UNRESOLVED_TYPED_CONFLICT:
        case DEF_CONFLICT_RESOLUTION_INSUFFICIENT:
            out->retrieval_purpose = RETRIEVAL_PURPOSE_CONFLICT_RESOLUTION;
            break;
        default:
            out->retrieval_purpose = RETRIEVAL_PURPOSE_OBJECT_LOOKUP;
            break;
    }

    out->target_object_kind = requirement->target_object_kind;
    memcpy(out->target_object_digest.bytes,
           requirement->target_object_digest.bytes, HACF_DIGEST_BYTES);

    out->requested_min_authority = requirement->minimum_authority;

    /* Query source is the overlay */
    out->query_source_kind = SOURCE_OVERLAY;
    memcpy(out->query_source_digest.bytes,
           query_overlay_digest->bytes, HACF_DIGEST_BYTES);

    out->requested_result_limit = 10; /* Default limit */

    /* Priority: mandatory > preferred > diagnostic */
    switch (requirement->requirement_level) {
        case MANDATORY:  out->requirement_priority_key = 3; break;
        case PREFERRED:  out->requirement_priority_key = 2; break;
        case DIAGNOSTIC: out->requirement_priority_key = 1; break;
        default:         out->requirement_priority_key = 0; break;
    }

    /* Compute identity */
    elpis_retrieval_requirement_identity(out, &out->retrieval_identity);

    return SEMANTIC_OK;
}
