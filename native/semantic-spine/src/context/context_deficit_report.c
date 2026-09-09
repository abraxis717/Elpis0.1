/* context_deficit_report.c — Deficit report identity and disposition.
 *
 * Identity domain: "elpis.semantic.context_deficit_report.v2"
 */
#include "elpis_semantic/context_deficit_report.h"
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

static const char DOMAIN[] = "elpis.semantic.context_deficit_report.v2";

void elpis_context_deficit_report_init(
    elpis_semantic_context_deficit_report_v1 *report) {
    memset(report, 0, sizeof(*report));
    report->abi_version = CONTEXT_DEFICIT_REPORT_ABI_VERSION;
}

int elpis_context_deficit_report_identity(
    const elpis_semantic_context_deficit_report_v1 *report, hacf_digest *out) {
    if (!report || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, DOMAIN);
    write_u32_be(&ctx, report->abi_version);
    write_digest(&ctx, &report->composed_view_digest);
    write_u32_be(&ctx, report->embedding_collection_count);
    for (uint32_t i = 0; i < report->embedding_collection_count; i++) {
        write_digest(&ctx, &report->embedding_collection_digests[i]);
    }
    write_digest(&ctx, &report->requirement_set_digest);
    write_digest(&ctx, &report->deficit_policy_digest);
    write_u32_be(&ctx, report->result_count);
    for (uint32_t i = 0; i < report->result_count; i++) {
        write_digest(&ctx, &report->per_requirement_result_digests[i]);
    }
    write_u32_be(&ctx, report->satisfied_count);
    write_u32_be(&ctx, report->mandatory_deficit_count);
    write_u32_be(&ctx, report->preferred_deficit_count);
    write_u32_be(&ctx, report->diagnostic_deficit_count);
    write_u32_be(&ctx, report->blocked_evaluation_count);
    write_u32_be(&ctx, report->overall_disposition);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_context_deficit_report_disposition(
    const elpis_semantic_requirement_result_v1 *results, uint32_t result_count,
    const elpis_semantic_context_requirement_set_v1 *requirement_set,
    const elpis_semantic_context_requirement_v1 *requirements,
    uint32_t requirement_count,
    const elpis_semantic_context_deficit_policy_v1 *policy,
    uint32_t *disposition_out) {
    if (!results || !requirement_set || !policy || !disposition_out) {
        return SEMANTIC_E_INVAL;
    }
    if (result_count == 0) {
        *disposition_out = DISP_EVALUATION_BLOCKED;
        return SEMANTIC_OK;
    }
    if (!requirements || result_count != requirement_count)
        return SEMANTIC_E_INVAL;

    if (elpis_context_requirement_set_validate(requirement_set) != SET_VALID) {
        *disposition_out = DISP_REQUIREMENT_SET_INVALID;
        return SEMANTIC_OK;
    }

    uint32_t satisfied = 0;
    uint32_t mandatory_deficit = 0;
    uint32_t preferred_deficit = 0;
    uint32_t diagnostic_deficit = 0;
    uint32_t blocked = 0;
    int rc = elpis_count_deficits(
        results, result_count, requirement_set, requirements, requirement_count,
        &satisfied, &mandatory_deficit, &preferred_deficit,
        &diagnostic_deficit, &blocked);
    if (rc != SEMANTIC_OK) return rc;

    (void)satisfied;
    (void)diagnostic_deficit;

    if (blocked > 0) {
        *disposition_out = DISP_EVALUATION_BLOCKED;
        return SEMANTIC_OK;
    }
    if (mandatory_deficit > 0) {
        *disposition_out = DISP_RETRIEVAL_REQUIRED;
        return SEMANTIC_OK;
    }
    if (preferred_deficit > 0 &&
        policy->preferred_failure_behavior == PREFERRED_BEHAVIOR_RETRIEVAL_REQUIRED) {
        *disposition_out = DISP_RETRIEVAL_REQUIRED;
        return SEMANTIC_OK;
    }

    *disposition_out = DISP_CONTEXT_SUFFICIENT;
    return SEMANTIC_OK;
}

int elpis_context_deficit_report_build(
    const hacf_digest                     *composed_view_digest,
    const elpis_semantic_embedding_collection_v1 *embedding_collections,
    uint32_t                                     collection_count,
    const elpis_semantic_context_requirement_set_v1 *requirement_set,
    const elpis_semantic_context_requirement_v1 *requirements,
    uint32_t requirement_count,
    const elpis_semantic_context_deficit_policy_v1  *policy,
    const elpis_semantic_requirement_result_v1 *results,
    uint32_t result_count,
    elpis_semantic_context_deficit_report_v1 **report_out) {
    if (!composed_view_digest || !requirement_set || !requirements || !policy ||
        !results || !report_out) {
        return SEMANTIC_E_INVAL;
    }
    if (collection_count > CONTEXT_MAX_EMBEDDING_COLLECTIONS ||
        result_count > CONTEXT_MAX_REQUIREMENTS ||
        requirement_count != result_count ||
        requirement_count != requirement_set->requirement_count) {
        return SEMANTIC_E_INVAL;
    }
    if (collection_count > 0 && !embedding_collections) {
        return SEMANTIC_E_INVAL;
    }
    if (memcmp(composed_view_digest,
               &requirement_set->target_composed_view_digest,
               HACF_DIGEST_BYTES) != 0) {
        return SEMANTIC_E_INVAL;
    }

    elpis_semantic_context_deficit_report_v1 *report =
        calloc(1, sizeof(elpis_semantic_context_deficit_report_v1));
    if (!report) return SEMANTIC_E_NOMEM;

    elpis_context_deficit_report_init(report);

    /* Bind the explicit evaluated-view identity. */
    memcpy(report->composed_view_digest.bytes,
           composed_view_digest->bytes, HACF_DIGEST_BYTES);

    /* Copy embedding collection digests */
    report->embedding_collection_count = collection_count;
    for (uint32_t i = 0; i < collection_count && i < CONTEXT_MAX_EMBEDDING_COLLECTIONS; i++) {
        memcpy(report->embedding_collection_digests[i].bytes,
               embedding_collections[i].collection_identity.bytes, HACF_DIGEST_BYTES);
    }

    /* Copy requirement set digest */
    memcpy(report->requirement_set_digest.bytes,
           requirement_set->requirement_set_identity.bytes, HACF_DIGEST_BYTES);

    /* Copy policy digest */
    memcpy(report->deficit_policy_digest.bytes,
           policy->policy_identity.bytes, HACF_DIGEST_BYTES);

    /* Copy per-result digests */
    report->result_count = result_count;
    for (uint32_t i = 0; i < result_count; i++) {
        memcpy(report->per_requirement_result_digests[i].bytes,
               results[i].diagnostic_digest.bytes, HACF_DIGEST_BYTES);
    }

    /* Count deficits from the exact bound requirement objects. */
    int rc = elpis_count_deficits(
        results, result_count, requirement_set, requirements, requirement_count,
        &report->satisfied_count,
        &report->mandatory_deficit_count,
        &report->preferred_deficit_count,
        &report->diagnostic_deficit_count,
        &report->blocked_evaluation_count);
    if (rc != SEMANTIC_OK) {
        free(report);
        return rc;
    }

    /* Determine disposition from the same exact binding. */
    rc = elpis_context_deficit_report_disposition(
        results, result_count, requirement_set, requirements, requirement_count,
        policy, &report->overall_disposition);
    if (rc != SEMANTIC_OK) {
        free(report);
        return rc;
    }

    /* Compute report identity */
    elpis_context_deficit_report_identity(report, &report->report_identity);

    *report_out = report;
    return SEMANTIC_OK;
}
