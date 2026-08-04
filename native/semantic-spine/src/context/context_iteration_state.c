


/* context_iteration_state.c — Context-iteration state and outcome adjudication. */
#include "elpis_semantic/context_iteration_state.h"
#include "elpis_semantic/identity.h"
#include <unistd.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include "elpis_semantic/context_iteration_policy.h"
#include "elpis_semantic/context_progress.h"
#include "elpis_semantic/context_deficit_report.h"
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





static const char *STATE_DOMAIN = "elpis.semantic.context_iteration_state.v1";

void elpis_context_iteration_state_init(
    elpis_semantic_context_iteration_state_v1 *state) {
    memset(state, 0, sizeof(*state));
    state->abi_version = CONTEXT_ITERATION_STATE_ABI_VERSION;
}

int elpis_context_iteration_state_round_zero(
    elpis_semantic_context_iteration_state_v1 *state,
    const hacf_digest *root_query_overlay_digest,
    const hacf_digest *initial_context_report_digest,
    const hacf_digest *iteration_policy_digest)
{
    if (!state || !root_query_overlay_digest ||
        !initial_context_report_digest || !iteration_policy_digest) {
        return SEMANTIC_E_INVAL;
    }

    elpis_context_iteration_state_init(state);

    memcpy(&state->root_query_overlay_digest, root_query_overlay_digest,
           HACF_DIGEST_BYTES);
    memcpy(&state->initial_context_report_digest, initial_context_report_digest,
           HACF_DIGEST_BYTES);
    /* Round 0 has no predecessor */
    memset(&state->previous_iteration_state_digest, 0, HACF_DIGEST_BYTES);
    state->round_index = 0;

    memcpy(&state->iteration_policy_digest, iteration_policy_digest,
           HACF_DIGEST_BYTES);

    /* Compute state identity */
    elpis_context_iteration_state_identity(state, &state->iteration_state_digest);
    return SEMANTIC_OK;
}

int elpis_context_iteration_state_advance(
    elpis_semantic_context_iteration_state_v1 *state,
    const elpis_semantic_context_iteration_state_v1 *previous,
    const hacf_digest *P3_retrieval_expansion_digest,
    const hacf_digest *P4_admission_layer_digest,
    const hacf_digest *P4_typed_evidence_view_digest,
    const hacf_digest *rebound_requirement_set_digest,
    const hacf_digest *P2_reevaluation_report_digest,
    const hacf_digest *P2_retrieval_requirement_bundle_digest,
    const hacf_digest *progress_report_digest)
{
    if (!state || !previous) return SEMANTIC_E_INVAL;
    if (previous->abi_version != CONTEXT_ITERATION_STATE_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* Monotonic round index */
    if (state->round_index != previous->round_index + 1)
        return SEMANTIC_E_INVAL;

    /* Same root overlay */
    if (memcmp(&state->root_query_overlay_digest,
               &previous->root_query_overlay_digest, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_E_INVAL;

    /* Same policy */
    if (memcmp(&state->iteration_policy_digest,
               &previous->iteration_policy_digest, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_E_INVAL;

    /* Non-cyclic predecessor */
    if (P3_retrieval_expansion_digest &&
        memcmp(&state->iteration_state_digest, P3_retrieval_expansion_digest,
               HACF_DIGEST_BYTES) == 0) {
        return SEMANTIC_E_INVAL;
    }

    /* Copy predecessor reference */
    memcpy(&state->previous_iteration_state_digest,
           &previous->iteration_state_digest, HACF_DIGEST_BYTES);

    /* Copy initial report from predecessor */
    memcpy(&state->initial_context_report_digest,
           &previous->initial_context_report_digest, HACF_DIGEST_BYTES);

    /* Set upstream digests */
    if (P3_retrieval_expansion_digest) {
        memcpy(&state->P3_retrieval_expansion_digest, P3_retrieval_expansion_digest,
               HACF_DIGEST_BYTES);
    }
    if (P4_admission_layer_digest) {
        memcpy(&state->P4_admission_layer_digest, P4_admission_layer_digest,
               HACF_DIGEST_BYTES);
    }
    if (P4_typed_evidence_view_digest) {
        memcpy(&state->P4_typed_evidence_view_digest, P4_typed_evidence_view_digest,
               HACF_DIGEST_BYTES);
    }
    if (rebound_requirement_set_digest) {
        memcpy(&state->rebound_requirement_set_digest, rebound_requirement_set_digest,
               HACF_DIGEST_BYTES);
    }
    if (P2_reevaluation_report_digest) {
        memcpy(&state->P2_reevaluation_report_digest, P2_reevaluation_report_digest,
               HACF_DIGEST_BYTES);
    }
    if (P2_retrieval_requirement_bundle_digest) {
        memcpy(&state->P2_retrieval_requirement_bundle_digest,
               P2_retrieval_requirement_bundle_digest, HACF_DIGEST_BYTES);
    }
    if (progress_report_digest) {
        memcpy(&state->progress_report_digest, progress_report_digest,
               HACF_DIGEST_BYTES);
    }

    /* Recompute state identity */
    elpis_context_iteration_state_identity(state, &state->iteration_state_digest);
    return SEMANTIC_OK;
}

int elpis_context_iteration_state_identity(
    const elpis_semantic_context_iteration_state_v1 *state, hacf_digest *out) {
    if (!state || !out ||
        state->abi_version != CONTEXT_ITERATION_STATE_ABI_VERSION) {
        return SEMANTIC_E_INVAL;
    }

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    write_domain_tag(&ctx, STATE_DOMAIN);

    uint32_t ver = state->abi_version;
    write_u32_be(&ctx, ver);

    elpis_sha256_update(&ctx, state->root_query_overlay_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, state->initial_context_report_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, state->previous_iteration_state_digest.bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, state->round_index);
    elpis_sha256_update(&ctx, state->P3_retrieval_expansion_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, state->P4_admission_layer_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, state->P4_typed_evidence_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, state->rebound_requirement_set_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, state->P2_reevaluation_report_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, state->P2_retrieval_requirement_bundle_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, state->progress_report_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, state->iteration_policy_digest.bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, state->iteration_outcome);

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_context_iteration_state_validate(
    const elpis_semantic_context_iteration_state_v1 *state) {
    if (!state) return SEMANTIC_E_INVAL;
    if (state->abi_version != CONTEXT_ITERATION_STATE_ABI_VERSION)
        return SEMANTIC_E_INVAL;

    /* Reserved zero */
    for (size_t i = 0; i < sizeof(state->reserved); i++) {
        if (state->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    /* Valid outcome */
    if (state->iteration_outcome > 7) return SEMANTIC_E_INVAL;

    return SEMANTIC_OK;
}

/* ── Outcome adjudication ── */

int elpis_context_iteration_outcome_adjudicate(
    const elpis_semantic_context_iteration_state_v1 *state,
    uint32_t P2_disposition,
    uint32_t progress_disposition,
    const elpis_semantic_context_iteration_policy_v1 *policy)
{
    if (!state || !policy) return SEMANTIC_E_INVAL;

    /* Case 1: Invalid requirement set */
    if (P2_disposition == DISP_REQUIREMENT_SET_INVALID) {
        return (int)OUTCOME_CONTEXT_REQUIREMENT_SET_INVALID;
    }

    /* Case 2: Evaluation blocked */
    if (P2_disposition == DISP_EVALUATION_BLOCKED) {
        return (int)OUTCOME_CONTEXT_REEVALUATION_BLOCKED;
    }

    /* Case 3: Context sufficient — zero blocked evaluations required */
    if (P2_disposition == DISP_CONTEXT_SUFFICIENT) {
        return (int)OUTCOME_CONTEXT_SUFFICIENT_AND_BOUNDED_VIEW_READY;
    }

    /* Cases 4-6: Retrieval required */
    if (P2_disposition == DISP_RETRIEVAL_REQUIRED) {
        /* Case 6: Round limit */
        if (state->round_index >= policy->maximum_retrieval_rounds) {
            return (int)OUTCOME_CONTEXT_ITERATION_STOPPED_ROUND_LIMIT;
    }

        /* Case 4: Progress */
        if (progress_disposition == PROGRESS_MEASURABLE_PROGRESS ||
            progress_disposition == PROGRESS_FIRST_EVALUATED_ROUND) {
            return (int)OUTCOME_RETRIEVAL_CONTINUATION_REQUIRED;
        }

        /* Case 5: No progress / stagnation */
        if (progress_disposition == PROGRESS_NO_PROGRESS_IDENTICAL_VIEW ||
            progress_disposition == PROGRESS_NO_PROGRESS_IDENTICAL_REQUIREMENTS ||
            progress_disposition == PROGRESS_NO_PROGRESS_IDENTICAL_DEFICITS ||
            progress_disposition == PROGRESS_NO_PROGRESS_NONCONTRIBUTING_EVIDENCE) {
            return (int)OUTCOME_CONTEXT_ITERATION_STOPPED_NO_PROGRESS;
        }
    }

    /* Unknown disposition — fail closed */
    return (int)OUTCOME_CONTEXT_REEVALUATION_BLOCKED;
}

/* ── Persistence ── */

int elpis_write_iteration_state(const char *path,
                                 const elpis_semantic_context_iteration_state_v1 *state) {
    if (!path || !state) return SEMANTIC_E_INVAL;
    return (int)p5_simple_write(path, (const uint8_t *)state, sizeof(*state));
}

int elpis_read_iteration_state(const char *path,
                                elpis_semantic_context_iteration_state_v1 *out) {
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

    int rc = elpis_context_iteration_state_validate(out);
    if (rc != SEMANTIC_OK) return rc;

    hacf_digest computed;
    elpis_context_iteration_state_identity(out, &computed);
    if (memcmp(&computed, &out->iteration_state_digest, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_E_DIGEST;
    return SEMANTIC_OK;
}
