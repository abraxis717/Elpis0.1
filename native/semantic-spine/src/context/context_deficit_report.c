/* context_deficit_report.c — Deficit report identity and disposition.
 *
 * Identity domain: "elpis.semantic.context_deficit_report.v1"
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

static const char DOMAIN[] = "elpis.semantic.context_deficit_report.v1";

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
    const elpis_semantic_context_deficit_policy_v1 *policy,
    uint32_t *disposition_out) {
    if (!results || !requirement_set || !policy || !disposition_out) {
        return SEMANTIC_E_INVAL;
    }
    if (result_count == 0) {
        *disposition_out = DISP_EVALUATION_BLOCKED;
        return SEMANTIC_OK;
    }

    uint32_t mandatory_deficit = 0;
    uint32_t preferred_deficit = 0;
    uint32_t diagnostic_deficit = 0;
    uint32_t blocked = 0;

    for (uint32_t i = 0; i < result_count; i++) {
        if (results[i].evaluation_status != EVAL_STATUS_EVALUATED) {
            blocked++;
            continue;
        }
        if (results[i].satisfaction_status == SAT_STATUS_UNSATISFIED) {
            /* In full implementation: look up the requirement level from the set */
            /* For now, classify all unsatisfied as mandatory (fail-safe) */
            mandatory_deficit++;
        }
        (void)diagnostic_deficit; /* suppress unused */
        (void)preferred_deficit; /* suppress unused */
    }

    /* Validation error → REQUIREMENT_SET_INVALID */
    if (elpis_context_requirement_set_validate(requirement_set) != SET_VALID) {
        *disposition_out = DISP_REQUIREMENT_SET_INVALID;
        return SEMANTIC_OK;
    }

    /* Blocked evaluations that prevent a valid report → EVALUATION_BLOCKED */
    if (blocked > 0) {
        /* Check if any blocked was for a mandatory requirement */
        /* For now: any blocked evaluation yields EVALUATION_BLOCKED (fail-safe) */
        *disposition_out = DISP_EVALUATION_BLOCKED;
        return SEMANTIC_OK;
    }

    /* Mandatory failure → RETRIEVAL_REQUIRED (policy mandates this) */
    if (mandatory_deficit > 0) {
        *disposition_out = DISP_RETRIEVAL_REQUIRED;
        return SEMANTIC_OK;
    }

    /* Preferred deficits may trigger retrieval if policy says so */
    if (preferred_deficit > 0 &&
        policy->preferred_failure_behavior == PREFERRED_BEHAVIOR_RETRIEVAL_REQUIRED) {
        *disposition_out = DISP_RETRIEVAL_REQUIRED;
        return SEMANTIC_OK;
    }

    /* All satisfied */
    *disposition_out = DISP_CONTEXT_SUFFICIENT;
    return SEMANTIC_OK;
}

int elpis_context_deficit_report_build(
    const semantic_snapshot_view          *composed_view,
    const elpis_semantic_embedding_collection_v1 *embedding_collections,
    uint32_t                                     collection_count,
    const elpis_semantic_context_requirement_set_v1 *requirement_set,
    const elpis_semantic_context_deficit_policy_v1  *policy,
    const elpis_semantic_requirement_result_v1 *results,
    uint32_t result_count,
    elpis_semantic_context_deficit_report_v1 **report_out) {
    if (!requirement_set || !policy || !results || !report_out) {
        return SEMANTIC_E_INVAL;
    }

    elpis_semantic_context_deficit_report_v1 *report =
        calloc(1, sizeof(elpis_semantic_context_deficit_report_v1));
    if (!report) return SEMANTIC_E_NOMEM;

    elpis_context_deficit_report_init(report);

    /* Copy composed view digest from requirement set target */
    memcpy(report->composed_view_digest.bytes,
           requirement_set->target_composed_view_digest.bytes, HACF_DIGEST_BYTES);

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

    /* Count deficits */
    elpis_count_deficits(results, result_count, requirement_set,
                         &report->satisfied_count,
                         &report->mandatory_deficit_count,
                         &report->preferred_deficit_count,
                         &report->diagnostic_deficit_count,
                         &report->blocked_evaluation_count);

    /* Determine disposition */
    elpis_context_deficit_report_disposition(results, result_count,
        requirement_set, policy, &report->overall_disposition);

    /* Compute report identity */
    elpis_context_deficit_report_identity(report, &report->report_identity);

    *report_out = report;
    return SEMANTIC_OK;
}
