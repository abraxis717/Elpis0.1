/* retrieval_requirement_bundle.c — Retrieval requirement bundle.
 *
 * Collects ordered retrieval requirements derived from a deficit report.
 * Identity domain: "elpis.semantic.retrieval_requirement_bundle.v1"
 */
#include "elpis_semantic/retrieval_requirement_bundle.h"
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

static const char DOMAIN[] = "elpis.semantic.retrieval_requirement_bundle.v1";

void elpis_retrieval_bundle_init(
    elpis_semantic_retrieval_requirement_bundle_v1 *bundle) {
    memset(bundle, 0, sizeof(*bundle));
    bundle->abi_version = RETRIEVAL_BUNDLE_ABI_VERSION;
}

int elpis_retrieval_bundle_add(
    elpis_semantic_retrieval_requirement_bundle_v1 *bundle,
    const hacf_digest *requirement_digest) {
    if (!bundle || !requirement_digest) return SEMANTIC_E_INVAL;
    if (bundle->retrieval_count >= CONTEXT_MAX_RETRIEVAL_REQUIREMENTS) return SEMANTIC_E_INVAL;

    /* Check for duplicate (exact collapse) */
    for (uint32_t i = 0; i < bundle->retrieval_count; i++) {
        if (memcmp(bundle->retrieval_requirement_digests[i].bytes,
                   requirement_digest->bytes, HACF_DIGEST_BYTES) == 0) {
            return SEMANTIC_E_DUPLICATE;
        }
    }

    /* Insert in sorted order (ascending by digest) */
    uint32_t insert_pos = bundle->retrieval_count;
    for (uint32_t i = 0; i < bundle->retrieval_count; i++) {
        if (memcmp(requirement_digest->bytes,
                   bundle->retrieval_requirement_digests[i].bytes,
                   HACF_DIGEST_BYTES) < 0) {
            insert_pos = i;
            break;
        }
    }
    for (uint32_t i = bundle->retrieval_count; i > insert_pos; i--) {
        bundle->retrieval_requirement_digests[i] =
            bundle->retrieval_requirement_digests[i - 1];
    }
    bundle->retrieval_requirement_digests[insert_pos] = *requirement_digest;
    bundle->retrieval_count++;
    return SEMANTIC_OK;
}

int elpis_retrieval_requirement_bundle_identity(
    const elpis_semantic_retrieval_requirement_bundle_v1 *bundle, hacf_digest *out) {
    if (!bundle || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, DOMAIN);
    write_u32_be(&ctx, bundle->abi_version);
    write_digest(&ctx, &bundle->context_deficit_report_digest);
    write_digest(&ctx, &bundle->composed_view_digest);
    write_digest(&ctx, &bundle->query_overlay_digest);
    write_digest(&ctx, &bundle->requirement_set_digest);
    write_digest(&ctx, &bundle->deficit_policy_digest);
    write_u32_be(&ctx, bundle->retrieval_count);
    for (uint32_t i = 0; i < bundle->retrieval_count; i++) {
        write_digest(&ctx, &bundle->retrieval_requirement_digests[i]);
    }
    write_digest(&ctx, &bundle->bundle_policy_digest);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_retrieval_bundle_validate(
    const elpis_semantic_retrieval_requirement_bundle_v1 *bundle) {
    if (!bundle) return SEMANTIC_E_INVAL;
    if (bundle->abi_version != RETRIEVAL_BUNDLE_ABI_VERSION) return SEMANTIC_E_INVAL;

    {
        static const uint8_t zero_buf[32];
        if (memcmp(bundle->reserved, zero_buf, sizeof(bundle->reserved)) != 0) {
            return SEMANTIC_E_RESERVATION;
        }
    }

    if (bundle->retrieval_count > CONTEXT_MAX_RETRIEVAL_REQUIREMENTS) return SEMANTIC_E_INVAL;

    /* Target digests must be non-zero */
    {
        static const uint8_t zero_digest[HACF_DIGEST_BYTES];
        if (memcmp(bundle->context_deficit_report_digest.bytes, zero_digest, HACF_DIGEST_BYTES) == 0) return SEMANTIC_E_INVAL;
    }

    /* Check digests sorted */
    for (uint32_t i = 1; i < bundle->retrieval_count; i++) {
        int cmp = memcmp(bundle->retrieval_requirement_digests[i].bytes,
                         bundle->retrieval_requirement_digests[i - 1].bytes,
                         HACF_DIGEST_BYTES);
        if (cmp < 0) return SEMANTIC_E_INVAL; /* not sorted */
        if (cmp == 0) return SEMANTIC_E_DUPLICATE;
    }

    return SEMANTIC_OK;
}

int elpis_retrieval_bundle_canonicalize(
    elpis_semantic_retrieval_requirement_bundle_v1 *bundle) {
    if (!bundle) return SEMANTIC_E_INVAL;
    /* Sort digests ascending (insertion sort) */
    for (uint32_t i = 1; i < bundle->retrieval_count; i++) {
        hacf_digest key = bundle->retrieval_requirement_digests[i];
        uint32_t j = i;
        while (j > 0 && memcmp(key.bytes,
                                bundle->retrieval_requirement_digests[j - 1].bytes,
                                HACF_DIGEST_BYTES) < 0) {
            bundle->retrieval_requirement_digests[j] =
                bundle->retrieval_requirement_digests[j - 1];
            j--;
        }
        bundle->retrieval_requirement_digests[j] = key;
    }
    return SEMANTIC_OK;
}

int elpis_retrieval_bundle_from_report(
    const elpis_semantic_context_deficit_report_v1   *report,
    const elpis_semantic_requirement_result_v1       *results,
    uint32_t                                          result_count,
    const elpis_semantic_context_requirement_set_v1  *requirement_set,
    const elpis_semantic_context_deficit_policy_v1   *policy,
    elpis_semantic_retrieval_requirement_bundle_v1   **bundle_out) {
    if (!report || !results || !requirement_set || !policy || !bundle_out) {
        return SEMANTIC_E_INVAL;
    }

    /* No bundle for CONTEXT_SUFFICIENT */
    if (report->overall_disposition == DISP_CONTEXT_SUFFICIENT) {
        return SEMANTIC_E_INVAL;
    }

    /* Evaluation blocked → cannot produce bundle */
    if (report->overall_disposition == DISP_EVALUATION_BLOCKED) {
        return SEMANTIC_E_INVAL;
    }

    elpis_semantic_retrieval_requirement_bundle_v1 *bundle =
        calloc(1, sizeof(elpis_semantic_retrieval_requirement_bundle_v1));
    if (!bundle) return SEMANTIC_E_NOMEM;

    elpis_retrieval_bundle_init(bundle);

    /* Copy report digest */
    memcpy(bundle->context_deficit_report_digest.bytes,
           report->report_identity.bytes, HACF_DIGEST_BYTES);

    /* Copy composed view digest */
    memcpy(bundle->composed_view_digest.bytes,
           report->composed_view_digest.bytes, HACF_DIGEST_BYTES);

    /* Copy query overlay from requirement set */
    memcpy(bundle->query_overlay_digest.bytes,
           requirement_set->target_query_overlay_digest.bytes, HACF_DIGEST_BYTES);

    /* Copy requirement set digest */
    memcpy(bundle->requirement_set_digest.bytes,
           requirement_set->requirement_set_identity.bytes, HACF_DIGEST_BYTES);

    /* Copy policy digest */
    memcpy(bundle->deficit_policy_digest.bytes,
           policy->policy_identity.bytes, HACF_DIGEST_BYTES);

    /* For each unsatisfied result, add a retrieval requirement digest */
    uint32_t max = policy->max_retrieval_requirements;
    for (uint32_t i = 0; i < result_count && bundle->retrieval_count < max; i++) {
        if (results[i].satisfaction_status == SAT_STATUS_UNSATISFIED) {
            /* Add the result diagnostic digest as the retrieval requirement digest */
            int ret = elpis_retrieval_bundle_add(bundle, &results[i].diagnostic_digest);
            if (ret == SEMANTIC_E_DUPLICATE) {
                /* Silently collapse */
                continue;
            }
            if (ret < 0) {
                free(bundle);
                return ret;
            }
        }
    }

    /* If we exceeded the limit, the caller gets an error via count check */
    if (bundle->retrieval_count >= max && result_count > 0) {
        /* Check if there are more deficits that couldn't be added */
        for (uint32_t i = 0; i < result_count; i++) {
            if (results[i].satisfaction_status == SAT_STATUS_UNSATISFIED) {
                int found = 0;
                for (uint32_t j = 0; j < bundle->retrieval_count; j++) {
                    if (memcmp(bundle->retrieval_requirement_digests[j].bytes,
                               results[i].diagnostic_digest.bytes,
                               HACF_DIGEST_BYTES) == 0) {
                        found = 1;
                        break;
                    }
                }
                if (!found) {
                    free(bundle);
                    return SEMANTIC_E_INVAL; /* limit exceeded */
                }
            }
        }
    }

    /* Canonicalize */
    elpis_retrieval_bundle_canonicalize(bundle);

    /* Compute identity */
    elpis_retrieval_requirement_bundle_identity(bundle, &bundle->bundle_identity);

    *bundle_out = bundle;
    return SEMANTIC_OK;
}
