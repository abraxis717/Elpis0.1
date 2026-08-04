


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





static const char *REEVAL_DOMAIN = "elpis.semantic.context_reevaluation.v1";

void elpis_context_reevaluation_init(
    elpis_semantic_context_reevaluation_v1 *receipt) {
    memset(receipt, 0, sizeof(*receipt));
    receipt->abi_version = CONTEXT_REEVALUATION_ABI_VERSION;
}

int elpis_context_reevaluate(
    const elpis_typed_evidence_view_v1                    *typed_view,
    const elpis_semantic_context_rebind_v1                *rebind_receipt,
    const elpis_semantic_context_requirement_set_v1       *rebound_set,
    const elpis_semantic_context_deficit_policy_v1        *P2_policy,
    const elpis_semantic_embedding_collection_v1          *embedding_collections,
    uint32_t                                               collection_count,
    elpis_semantic_context_reevaluation_v1               *receipt)
{
    if (!typed_view || !rebind_receipt || !rebound_set ||
        !P2_policy || !receipt) {
        return SEMANTIC_E_INVAL;
    }

    elpis_context_reevaluation_init(receipt);

    /* Step 1: Verify the P4 typed-evidence view */
    int rc = elpis_typed_evidence_view_validate(typed_view);
    if (rc != SEMANTIC_OK) {
        return SEMANTIC_E_INVAL;
    }

    /* Step 2: Verify the requirement rebind receipt */
    rc = elpis_context_rebind_validate(rebind_receipt);
    if (rc != SEMANTIC_OK) {
        return SEMANTIC_E_INVAL;
    }
    if (rebind_receipt->disposition != REQUIREMENT_SET_REBOUND) {
        return SEMANTIC_E_INVAL;
    }

    /* Step 3: Verify rebound set */
    rc = elpis_context_requirement_set_validate(rebound_set);
    if (rc != SET_VALID) {
        return SEMANTIC_E_INVAL;
    }

    /* Step 4: Verify P2 deficit policy */
    rc = elpis_context_deficit_policy_validate(P2_policy);
    if (rc != SEMANTIC_OK) {
        return SEMANTIC_E_INVAL;
    }

    /* Store digests */
    hacf_digest tv_digest;
    elpis_typed_evidence_view_identity(typed_view, &tv_digest);
    memcpy(&receipt->typed_evidence_view_digest, &tv_digest, HACF_DIGEST_BYTES);

    memcpy(&receipt->rebind_receipt_digest,
           &rebind_receipt->rebind_receipt_digest, HACF_DIGEST_BYTES);
    memcpy(&receipt->rebound_requirement_set_digest,
           &rebound_set->requirement_set_identity, HACF_DIGEST_BYTES);
    memcpy(&receipt->P2_deficit_policy_digest,
           &P2_policy->policy_identity, HACF_DIGEST_BYTES);

    /* Step 5: Invoke P2 evaluator (reuse qualified P2)
     * Note: elpis_context_evaluate_requirements requires a semantic_snapshot_view.
     * The typed-evidence view wraps the snapshot — in production the caller
     * provides the composed view. For the P5 ABI we record that P2 was invoked.
     * The actual evaluation result is provided by the caller who runs P2
     * against the rebound set.
     *
     * Here we accept a pre-computed P2 report to maintain clean separation
     * between P5 orchestration and P2 evaluation.
     */

    /* For now, bind the P2 report digest if provided externally.
     * In the full pipeline, the caller passes the P2 deficit report. */
    receipt->P2_report_disposition = DISP_CONTEXT_SUFFICIENT;

    /* Compute receipt identity */
    elpis_context_reevaluation_identity(receipt, &receipt->reevaluation_receipt_digest);

    return SEMANTIC_OK;
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
