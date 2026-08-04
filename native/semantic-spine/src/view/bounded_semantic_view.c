


/* bounded_semantic_view.c — Bounded semantic view construction for P5. */
#include "elpis_semantic/bounded_semantic_view.h"
#include "elpis_semantic/identity.h"
#include <unistd.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include "elpis_semantic/bounded_view_seed.h"
#include "elpis_semantic/bounded_view_candidate.h"
#include "elpis_semantic/bounded_view_policy.h"
#include "elpis_semantic/context_reevaluation.h"
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





static const char *VIEW_DOMAIN = "elpis.semantic.bounded_semantic_view.v1";

void elpis_bounded_semantic_view_init(
    elpis_semantic_bounded_semantic_view_v1 *view) {
    memset(view, 0, sizeof(*view));
    view->abi_version = BOUNDED_SEMANTIC_VIEW_ABI_VERSION;
}

int elpis_bounded_semantic_view_construct(
    const elpis_typed_evidence_view_v1                *typed_view,
    const elpis_semantic_bounded_view_seed_set_v1    *seed_set,
    const elpis_semantic_bounded_view_candidate_set_v1 *candidate_set,
    const elpis_semantic_bounded_view_policy_v1      *policy,
    const elpis_semantic_context_reevaluation_v1     *reevaluation,
    elpis_semantic_bounded_semantic_view_v1          *view)
{
    if (!typed_view || !seed_set || !candidate_set || !policy || !reevaluation
        || !view) {
        return SEMANTIC_E_INVAL;
    }

    /* Rank candidates deterministically first */
    elpis_semantic_bounded_view_candidate_set_v1 ranked = *candidate_set;
    elpis_bounded_view_rank_candidates(&ranked);

    /* Compute mandatory closure */
    int rc = elpis_bounded_view_compute_mandatory_closure(
        typed_view, seed_set, &ranked, policy, view);
    if (rc != SEMANTIC_OK) {
        return rc; /* May be BOUNDED_VIEW_BLOCKED_BY_CAPACITY */
    }

    /* Bind upstream references */
    memcpy(&view->P5_reevaluation_receipt_digest,
           &reevaluation->reevaluation_receipt_digest, HACF_DIGEST_BYTES);
    memcpy(&view->P2_deficit_report_digest,
           &reevaluation->P2_deficit_report_digest, HACF_DIGEST_BYTES);
    memcpy(&view->rebound_requirement_set_digest,
           &seed_set->rebound_requirement_set_digest, HACF_DIGEST_BYTES);
    memcpy(&view->seed_set_digest,
           &seed_set->seed_set_digest, HACF_DIGEST_BYTES);
    memcpy(&view->bounded_view_policy_digest,
           &policy->policy_identity, HACF_DIGEST_BYTES);

    /* Now fill optional candidates from ranked list until capacity */
    uint32_t node_budget = policy->maximum_semantic_nodes - view->semantic_node_count;
    uint32_t assertion_budget = policy->maximum_assertions - view->assertion_count;

    uint32_t omission_count = 0;

    for (uint32_t i = 0; i < ranked.candidate_count; i++) {
        const bounded_view_candidate_record *c = &ranked.ordered_candidates[i];

        /* Skip if already included (mandatory) */
        if (c->origin_kind == CANDIDATE_ORIGIN_MANDATORY_SEED) continue;

        /* Check if optional admission is possible */
        if (node_budget > 0 && assertion_budget > 0) {
            /* Check if this candidate's object is already in the node list */
            int already = 0;
            for (uint32_t n = 0; n < view->semantic_node_count; n++) {
                if (memcmp(&c->object_digest,
                           &view->ordered_semantic_node_digests[n],
                           HACF_DIGEST_BYTES) == 0) {
                    already = 1; break;
                }
            }
            if (!already) {
                /* Admit as optional */
                view->ordered_semantic_node_digests[view->semantic_node_count]
                    = c->object_digest;
                view->semantic_node_count++;
                node_budget--;
                view->ordered_inclusion_record_digests[view->inclusion_record_count]
                    = c->candidate_record_digest;
                view->inclusion_record_count++;
            }
        } else {
            /* Omit — record omission reason */
            if (omission_count < BOUNDED_VIEW_MAX_PLANE_DIGEST_ENTRIES) {
                view->ordered_omission_record_digests[omission_count]
                    = c->candidate_record_digest;
                omission_count++;
            }
        }
    }

    view->omission_record_count = omission_count;

    /* Recompute plane digests */
    elpis_sha256_ctx ctx;

    /* Semantic plane */
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.plane.semantic.v1");
    write_u32_be(&ctx, view->semantic_node_count);
    for (uint32_t i = 0; i < view->semantic_node_count; i++)
        elpis_sha256_update(&ctx, view->ordered_semantic_node_digests[i].bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, view->semantic_hyperedge_count);
    for (uint32_t i = 0; i < view->semantic_hyperedge_count; i++)
        elpis_sha256_update(&ctx, view->ordered_semantic_hyperedge_digests[i].bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, view->semantic_plane_digest.bytes);

    /* Provenance plane */
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.plane.provenance.v1");
    write_u32_be(&ctx, view->assertion_count);
    for (uint32_t i = 0; i < view->assertion_count; i++)
        elpis_sha256_update(&ctx, view->ordered_assertion_digests[i].bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, view->source_span_count);
    for (uint32_t i = 0; i < view->source_span_count; i++)
        elpis_sha256_update(&ctx, view->ordered_source_span_digests[i].bytes, HACF_DIGEST_BYTES);
    uint32_t status = 0; /* UNAVAILABLE */
    write_u32_be(&ctx, status);
    elpis_sha256_final(&ctx, view->provenance_plane_digest.bytes);

    /* Metric plane */
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.plane.metric.v1");
    write_u32_be(&ctx, view->embedding_reference_count);
    for (uint32_t i = 0; i < view->embedding_reference_count; i++)
        elpis_sha256_update(&ctx, view->ordered_embedding_reference_digests[i].bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, view->metric_observation_count);
    elpis_sha256_final(&ctx, view->metric_plane_digest.bytes);

    /* Control plane */
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.plane.control.v1");
    write_u32_be(&ctx, view->inclusion_record_count);
    for (uint32_t i = 0; i < view->inclusion_record_count; i++)
        elpis_sha256_update(&ctx, view->ordered_inclusion_record_digests[i].bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, view->omission_record_count);
    for (uint32_t i = 0; i < view->omission_record_count; i++)
        elpis_sha256_update(&ctx, view->ordered_omission_record_digests[i].bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, view->control_plane_digest.bytes);

    /* Compute bounded view identity */
    elpis_bounded_semantic_view_identity(view, &view->bounded_view_digest);

    return SEMANTIC_OK;
}

int elpis_bounded_semantic_view_identity(
    const elpis_semantic_bounded_semantic_view_v1 *view, hacf_digest *out) {
    if (!view || !out ||
        view->abi_version != BOUNDED_SEMANTIC_VIEW_ABI_VERSION)
        return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, VIEW_DOMAIN);
    uint32_t ver = view->abi_version;
    write_u32_be(&ctx, ver);
    elpis_sha256_update(&ctx, view->root_query_overlay_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, view->P4_typed_evidence_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, view->P5_reevaluation_receipt_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, view->P2_deficit_report_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, view->rebound_requirement_set_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, view->seed_set_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, view->bounded_view_policy_digest.bytes, HACF_DIGEST_BYTES);
    /* Semantic plane digests */
    elpis_sha256_update(&ctx, view->semantic_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, view->provenance_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, view->metric_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, view->control_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_bounded_semantic_view_validate(
    const elpis_semantic_bounded_semantic_view_v1 *view) {
    if (!view) return SEMANTIC_E_INVAL;
    if (view->abi_version != BOUNDED_SEMANTIC_VIEW_ABI_VERSION)
        return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(view->reserved); i++) {
        if (view->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    /* Plane digests must resolve (non-zero) */
    for (int i = 0; i < HACF_DIGEST_BYTES; i++) {
        if (view->semantic_plane_digest.bytes[i] != 0) break;
        if (i == HACF_DIGEST_BYTES - 1) return SEMANTIC_E_INVAL;
    }
    for (int i = 0; i < HACF_DIGEST_BYTES; i++) {
        if (view->provenance_plane_digest.bytes[i] != 0) break;
        if (i == HACF_DIGEST_BYTES - 1) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_bounded_semantic_view(const char *path,
    const elpis_semantic_bounded_semantic_view_v1 *view) {
    if (!path || !view) return SEMANTIC_E_INVAL;
    return (int)p5_simple_write(path, (const uint8_t *)view, sizeof(*view));
}

int elpis_read_bounded_semantic_view(const char *path,
    elpis_semantic_bounded_semantic_view_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;
    fseek(f, 0, SEEK_END); long sz = ftell(f);
    if (sz != (long)sizeof(*out)) { fclose(f); return SEMANTIC_E_IO; }
    fseek(f, 0, SEEK_SET); size_t rd = fread(out, 1, sizeof(*out), f);
    fclose(f); if (rd != sizeof(*out)) return SEMANTIC_E_IO;
    int rc = elpis_bounded_semantic_view_validate(out);
    if (rc != SEMANTIC_OK) return rc;
    hacf_digest computed;
    elpis_bounded_semantic_view_identity(out, &computed);
    if (memcmp(&computed, &out->bounded_view_digest, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_E_DIGEST;
    return SEMANTIC_OK;
}
