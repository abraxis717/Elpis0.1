


/* context_progress.c — Progress measurement for P5 iteration. */
#include "elpis_semantic/context_progress.h"
#include "elpis_semantic/identity.h"
#include <unistd.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include "elpis_semantic/context_deficit.h"
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





static const char *PROGRESS_DOMAIN = "elpis.semantic.context_progress.v1";

void elpis_context_progress_init(elpis_semantic_context_progress_v1 *report) {
    memset(report, 0, sizeof(*report));
    report->abi_version = CONTEXT_PROGRESS_ABI_VERSION;
}

int elpis_context_measure_progress(
    const elpis_semantic_context_progress_v1 *previous_inputs,
    const elpis_semantic_context_progress_v1 *current_inputs,
    const elpis_semantic_requirement_result_v1 *previous_results,
    uint32_t previous_result_count,
    const elpis_semantic_requirement_result_v1 *current_results,
    uint32_t current_result_count,
    elpis_semantic_context_progress_v1 *report)
{
    if (!report) return SEMANTIC_E_INVAL;

    elpis_context_progress_init(report);

    if (previous_inputs) {
        memcpy(&report->previous_iteration_state_digest,
               &previous_inputs->previous_iteration_state_digest, HACF_DIGEST_BYTES);
    }
    if (current_inputs) {
        memcpy(&report->current_iteration_state_inputs_digest,
               &current_inputs->current_iteration_state_inputs_digest, HACF_DIGEST_BYTES);
    }

    /* Determine if this is the first evaluated round */
    int is_first_round = 0;
    if (!previous_results || previous_result_count == 0) {
        is_first_round = 1;
    }

    if (is_first_round) {
        report->progress_disposition = PROGRESS_FIRST_EVALUATED_ROUND;
        elpis_context_progress_identity(report, &report->progress_report_digest);
        return SEMANTIC_OK;
    }

    /* Detect identical typed-evidence view */
    if (previous_inputs && current_inputs) {
        int identical_view = (memcmp(&previous_inputs->previous_typed_evidence_view_digest,
                                     &current_inputs->current_typed_evidence_view_digest,
                                     HACF_DIGEST_BYTES) == 0);
        if (identical_view) {
            report->progress_disposition = PROGRESS_NO_PROGRESS_IDENTICAL_VIEW;
            elpis_context_progress_identity(report, &report->progress_report_digest);
            return SEMANTIC_OK;
        }
    }

    /* Detect identical requirement bundle */
    if (previous_inputs && current_inputs) {
        int identical_bundle = (memcmp(&previous_inputs->previous_retrieval_requirement_bundle_digest,
                                       &current_inputs->current_retrieval_requirement_bundle_digest,
                                       HACF_DIGEST_BYTES) == 0);
        if (identical_bundle) {
            report->progress_disposition = PROGRESS_NO_PROGRESS_IDENTICAL_REQUIREMENTS;
            elpis_context_progress_identity(report, &report->progress_report_digest);
            return SEMANTIC_OK;
        }
    }

    /* Measure deficit delta */
    uint32_t resolved_mandatory = 0;
    uint32_t new_mandatory = 0;
    uint32_t unchanged_mandatory = 0;
    uint32_t contributing_delta = 0;

    for (uint32_t i = 0; i < current_result_count; i++) {
        /* Find matching previous result by requirement digest */
        const elpis_semantic_requirement_result_v1 *prev = NULL;
        for (uint32_t j = 0; j < previous_result_count; j++) {
            if (memcmp(&current_results[i].requirement_digest,
                       &previous_results[j].requirement_digest,
                       HACF_DIGEST_BYTES) == 0) {
                prev = &previous_results[j];
                break;
            }
        }

        if (prev) {
            /* Resolved: previously unsatisfied, now satisfied */
            if (prev->satisfaction_status == SAT_STATUS_UNSATISFIED &&
                current_results[i].satisfaction_status == SAT_STATUS_SATISFIED) {
                resolved_mandatory++;
                contributing_delta++;
            }
            /* New deficit: previously satisfied, now unsatisfied */
            else if (prev->satisfaction_status == SAT_STATUS_SATISFIED &&
                     current_results[i].satisfaction_status == SAT_STATUS_UNSATISFIED) {
                new_mandatory++;
            }
            /* Unchanged unsatisfied */
            else if (prev->satisfaction_status == SAT_STATUS_UNSATISFIED &&
                     current_results[i].satisfaction_status == SAT_STATUS_UNSATISFIED) {
                unchanged_mandatory++;
            }
        } else {
            /* New requirement — count as contributing if satisfied */
            if (current_results[i].satisfaction_status == SAT_STATUS_SATISFIED) {
                contributing_delta++;
            }
        }
    }

    report->resolved_mandatory_deficit_count = resolved_mandatory;
    report->new_mandatory_deficit_count = new_mandatory;
    report->unchanged_mandatory_deficit_count = unchanged_mandatory;
    report->contributing_semantic_delta_count = contributing_delta;

    /* Detect identical deficit set */
    if (previous_inputs && current_inputs) {
        int identical_deficits = (memcmp(&previous_inputs->previous_deficit_report_digest,
                                         &current_inputs->current_deficit_report_digest,
                                         HACF_DIGEST_BYTES) == 0);
        if (identical_deficits && contributing_delta == 0) {
            report->progress_disposition = PROGRESS_NO_PROGRESS_IDENTICAL_DEFICITS;
            elpis_context_progress_identity(report, &report->progress_report_digest);
            return SEMANTIC_OK;
        }
    }

    /* Non-contributing evidence */
    if (contributing_delta == 0) {
        report->progress_disposition = PROGRESS_NO_PROGRESS_NONCONTRIBUTING_EVIDENCE;
        elpis_context_progress_identity(report, &report->progress_report_digest);
        return SEMANTIC_OK;
    }

    /* Measurable progress */
    report->progress_disposition = PROGRESS_MEASURABLE_PROGRESS;
    elpis_context_progress_identity(report, &report->progress_report_digest);
    return SEMANTIC_OK;
}

int elpis_context_progress_identity(
    const elpis_semantic_context_progress_v1 *report, hacf_digest *out) {
    if (!report || !out ||
        report->abi_version != CONTEXT_PROGRESS_ABI_VERSION) {
        return SEMANTIC_E_INVAL;
    }

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    write_domain_tag(&ctx, PROGRESS_DOMAIN);

    uint32_t ver = report->abi_version;
    write_u32_be(&ctx, ver);

    elpis_sha256_update(&ctx, report->previous_iteration_state_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, report->current_iteration_state_inputs_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, report->previous_typed_evidence_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, report->current_typed_evidence_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, report->previous_deficit_report_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, report->current_deficit_report_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, report->previous_retrieval_requirement_bundle_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, report->current_retrieval_requirement_bundle_digest.bytes, HACF_DIGEST_BYTES);

    write_u32_be(&ctx, report->new_semantic_node_count);
    write_u32_be(&ctx, report->new_semantic_hyperedge_count);
    write_u32_be(&ctx, report->new_assertion_count);
    write_u32_be(&ctx, report->new_evidence_span_count);
    write_u32_be(&ctx, report->new_requirement_satisfaction_count);
    write_u32_be(&ctx, report->resolved_mandatory_deficit_count);
    write_u32_be(&ctx, report->new_mandatory_deficit_count);
    write_u32_be(&ctx, report->unchanged_mandatory_deficit_count);
    write_u32_be(&ctx, report->contributing_semantic_delta_count);
    write_u32_be(&ctx, report->stagnant_round_count);
    write_u32_be(&ctx, report->progress_disposition);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_context_progress_validate(
    const elpis_semantic_context_progress_v1 *report) {
    if (!report) return SEMANTIC_E_INVAL;
    if (report->abi_version != CONTEXT_PROGRESS_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    for (size_t i = 0; i < sizeof(report->reserved); i++) {
        if (report->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    if (report->progress_disposition > 6) return SEMANTIC_E_INVAL;

    return SEMANTIC_OK;
}

int elpis_write_context_progress(const char *path,
                                  const elpis_semantic_context_progress_v1 *report) {
    if (!path || !report) return SEMANTIC_E_INVAL;
    return (int)p5_simple_write(path, (const uint8_t *)report, sizeof(*report));
}

int elpis_read_context_progress(const char *path,
                                 elpis_semantic_context_progress_v1 *out) {
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

    int rc = elpis_context_progress_validate(out);
    if (rc != SEMANTIC_OK) return rc;

    hacf_digest computed;
    elpis_context_progress_identity(out, &computed);
    if (memcmp(&computed, &out->progress_report_digest, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_E_DIGEST;
    return SEMANTIC_OK;
}
