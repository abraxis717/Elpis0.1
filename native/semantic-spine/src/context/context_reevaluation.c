


/* context_reevaluation.c — Post-admission context re-evaluation. */
#include "elpis_semantic/context_reevaluation.h"
#include "elpis_semantic/identity.h"
#include <unistd.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include "elpis_semantic/context_rebind.h"
#include "elpis_semantic/context_deficit_report.h"
#include "elpis_semantic/typed_evidence_view.h"
#include "elpis/sha256.h"
#include <string.h>
#include <stdint.h>
#include <arpa/inet.h>
#include <stdio.h>

/* Simple atomic write — declared in p5_writer.c */
extern int p5_simple_write(const char *path, const uint8_t *data, size_t sz);

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





static const char *REEVAL_DOMAIN = "elpis.semantic.context_reevaluation.v2";

void elpis_context_reevaluation_init(
    elpis_semantic_context_reevaluation_v1 *receipt) {
    memset(receipt, 0, sizeof(*receipt));
    receipt->abi_version = CONTEXT_REEVALUATION_ABI_VERSION;
}

static int digest_equal(const hacf_digest *a, const hacf_digest *b) {
    return memcmp(a->bytes, b->bytes, HACF_DIGEST_BYTES) == 0;
}

static int validate_p2_report_binding(
    const elpis_semantic_context_deficit_report_v1 *report,
    const elpis_typed_evidence_view_v1 *typed_view,
    const hacf_digest *typed_view_digest,
    const elpis_semantic_context_requirement_set_v1 *rebound_set,
    const elpis_semantic_context_deficit_policy_v1 *policy)
{
    if (!report || !typed_view || !typed_view_digest || !rebound_set || !policy)
        return SEMANTIC_E_INVAL;
    if (report->abi_version != CONTEXT_DEFICIT_REPORT_ABI_VERSION)
        return SEMANTIC_E_INVAL;
    if (report->embedding_collection_count > CONTEXT_MAX_EMBEDDING_COLLECTIONS ||
        report->result_count > CONTEXT_MAX_REQUIREMENTS)
        return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(report->reserved); ++i) {
        if (report->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    if (report->overall_disposition < DISP_CONTEXT_SUFFICIENT ||
        report->overall_disposition > DISP_EVALUATION_BLOCKED)
        return SEMANTIC_E_INVAL;
    if (!digest_equal(&report->composed_view_digest, typed_view_digest) ||
        !digest_equal(&report->requirement_set_digest,
                      &rebound_set->requirement_set_identity) ||
        !digest_equal(&report->deficit_policy_digest, &policy->policy_identity))
        return SEMANTIC_E_INVAL;
    if (report->embedding_collection_count != typed_view->embedding_collection_count)
        return SEMANTIC_E_INVAL;
    for (uint32_t i = 0; i < report->embedding_collection_count; ++i) {
        if (!digest_equal(&report->embedding_collection_digests[i],
                          &typed_view->embedding_collection_digests[i]))
            return SEMANTIC_E_INVAL;
    }
    if (report->result_count != rebound_set->requirement_count)
        return SEMANTIC_E_INVAL;

    hacf_digest computed;
    if (elpis_context_deficit_report_identity(report, &computed) != SEMANTIC_OK)
        return SEMANTIC_E_INVAL;
    return digest_equal(&computed, &report->report_identity)
        ? SEMANTIC_OK : SEMANTIC_E_DIGEST;
}

int elpis_context_reevaluate(
    const elpis_typed_evidence_view_v1                    *typed_view,
    const elpis_semantic_context_rebind_v1                *rebind_receipt,
    const elpis_semantic_context_requirement_set_v1       *rebound_set,
    const elpis_semantic_context_deficit_policy_v1        *P2_policy,
    const elpis_semantic_context_deficit_report_v1        *P2_report,
    elpis_semantic_context_reevaluation_v1               *receipt)
{
    if (!typed_view || !rebind_receipt || !rebound_set ||
        !P2_policy || !P2_report || !receipt) {
        return SEMANTIC_E_INVAL;
    }

    elpis_context_reevaluation_init(receipt);

    if (elpis_typed_evidence_view_validate(typed_view) != SEMANTIC_OK)
        return SEMANTIC_E_INVAL;

    hacf_digest tv_digest;
    if (elpis_typed_evidence_view_identity(typed_view, &tv_digest) != SEMANTIC_OK ||
        !digest_equal(&tv_digest, &typed_view->typed_evidence_view_digest))
        return SEMANTIC_E_DIGEST;

    if (elpis_context_rebind_validate(rebind_receipt) != SEMANTIC_OK ||
        rebind_receipt->disposition != REQUIREMENT_SET_REBOUND)
        return SEMANTIC_E_INVAL;

    hacf_digest rebind_digest;
    if (elpis_context_rebind_identity(rebind_receipt, &rebind_digest) != SEMANTIC_OK ||
        !digest_equal(&rebind_digest, &rebind_receipt->rebind_receipt_digest))
        return SEMANTIC_E_DIGEST;

    if (elpis_context_requirement_set_validate(rebound_set) != SET_VALID)
        return SEMANTIC_E_INVAL;

    hacf_digest rebound_digest;
    if (elpis_context_requirement_set_identity(rebound_set, &rebound_digest) != SEMANTIC_OK ||
        !digest_equal(&rebound_digest, &rebound_set->requirement_set_identity))
        return SEMANTIC_E_DIGEST;

    if (!digest_equal(&rebind_receipt->new_typed_evidence_view_digest, &tv_digest) ||
        !digest_equal(&rebind_receipt->rebound_requirement_set_digest, &rebound_digest) ||
        !digest_equal(&rebound_set->target_composed_view_digest, &tv_digest))
        return SEMANTIC_E_INVAL;

    if (elpis_context_deficit_policy_validate(P2_policy) != SEMANTIC_OK)
        return SEMANTIC_E_INVAL;

    hacf_digest policy_digest;
    if (elpis_context_deficit_policy_identity(P2_policy, &policy_digest) != SEMANTIC_OK ||
        !digest_equal(&policy_digest, &P2_policy->policy_identity))
        return SEMANTIC_E_DIGEST;

    int rc = validate_p2_report_binding(
        P2_report, typed_view, &tv_digest, rebound_set, P2_policy);
    if (rc != SEMANTIC_OK) return rc;

    receipt->typed_evidence_view_digest = tv_digest;
    receipt->rebind_receipt_digest = rebind_digest;
    receipt->rebound_requirement_set_digest = rebound_digest;
    receipt->P2_deficit_policy_digest = policy_digest;
    receipt->P2_deficit_report_digest = P2_report->report_identity;
    receipt->P2_report_disposition = P2_report->overall_disposition;

    /* P2 report v1 does not expose satisfied-mandatory count separately. */
    receipt->satisfied_mandatory_count = 0;
    receipt->unsatisfied_mandatory_count = P2_report->mandatory_deficit_count;
    receipt->unsatisfied_preferred_count = P2_report->preferred_deficit_count;
    receipt->diagnostic_deficit_count = P2_report->diagnostic_deficit_count;
    receipt->blocked_evaluation_count = P2_report->blocked_evaluation_count;

    /* P2 report v1 carries no retrieval-requirement-bundle identity. */
    memset(&receipt->P2_retrieval_requirement_bundle_digest, 0,
           sizeof(receipt->P2_retrieval_requirement_bundle_digest));

    if (elpis_context_reevaluation_identity(
            receipt, &receipt->reevaluation_receipt_digest) != SEMANTIC_OK)
        return SEMANTIC_E_INVAL;

    return elpis_context_reevaluation_validate(receipt);
}

int elpis_context_reevaluation_identity(
    const elpis_semantic_context_reevaluation_v1 *receipt, hacf_digest *out) {
    if (!receipt || !out ||
        receipt->abi_version != CONTEXT_REEVALUATION_ABI_VERSION) {
        return SEMANTIC_E_INVAL;
    }

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    write_domain_tag(&ctx, REEVAL_DOMAIN);

    uint32_t ver = receipt->abi_version;
    write_u32_be(&ctx, ver);

    elpis_sha256_update(&ctx, receipt->typed_evidence_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->rebind_receipt_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->rebound_requirement_set_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->P2_deficit_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, receipt->P2_deficit_report_digest.bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, receipt->P2_report_disposition);
    elpis_sha256_update(&ctx, receipt->P2_retrieval_requirement_bundle_digest.bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, receipt->satisfied_mandatory_count);
    write_u32_be(&ctx, receipt->unsatisfied_mandatory_count);
    write_u32_be(&ctx, receipt->unsatisfied_preferred_count);
    write_u32_be(&ctx, receipt->diagnostic_deficit_count);
    write_u32_be(&ctx, receipt->blocked_evaluation_count);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_context_reevaluation_validate(
    const elpis_semantic_context_reevaluation_v1 *receipt) {
    if (!receipt) return SEMANTIC_E_INVAL;
    if (receipt->abi_version != CONTEXT_REEVALUATION_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    for (size_t i = 0; i < sizeof(receipt->reserved); i++) {
        if (receipt->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    /* Valid disposition */
    if (receipt->P2_report_disposition < DISP_CONTEXT_SUFFICIENT ||
        receipt->P2_report_disposition > DISP_EVALUATION_BLOCKED) {
        return SEMANTIC_E_INVAL;
    }

    return SEMANTIC_OK;
}

/* ── Persistence ── */

int elpis_write_context_reevaluation(const char *path,
                                      const elpis_semantic_context_reevaluation_v1 *receipt) {
    if (!path || !receipt) return SEMANTIC_E_INVAL;
    return (int)p5_simple_write(path, (const uint8_t *)receipt, sizeof(*receipt));
}

int elpis_read_context_reevaluation(const char *path,
                                     elpis_semantic_context_reevaluation_v1 *out) {
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

    int rc = elpis_context_reevaluation_validate(out);
    if (rc != SEMANTIC_OK) return rc;

    hacf_digest computed;
    elpis_context_reevaluation_identity(out, &computed);
    if (memcmp(&computed, &out->reevaluation_receipt_digest, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_E_DIGEST;
    return SEMANTIC_OK;
}
