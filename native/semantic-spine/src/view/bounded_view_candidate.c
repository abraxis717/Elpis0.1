


/* bounded_view_candidate.c — Bounded-view candidate enumeration for P5. */
#include "elpis_semantic/bounded_view_candidate.h"
#include "elpis_semantic/identity.h"
#include <unistd.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include "elpis_semantic/bounded_view_policy.h"
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





static const char *CANDIDATE_DOMAIN = "elpis.semantic.bounded_view_candidate_set.v1";

void elpis_bounded_view_candidate_set_init(
    elpis_semantic_bounded_view_candidate_set_v1 *set) {
    memset(set, 0, sizeof(*set));
    set->abi_version = BOUNDED_VIEW_CANDIDATE_ABI_VERSION;
}

int elpis_bounded_view_candidate_record_digest(
    const bounded_view_candidate_record *rec, hacf_digest *out) {
    if (!rec || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.bounded_view_candidate.v1");
    write_u32_be(&ctx, rec->object_kind);
    elpis_sha256_update(&ctx, rec->object_digest.bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, rec->origin_kind);
    elpis_sha256_update(&ctx, rec->origin_seed_digest.bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, rec->graph_hop);
    write_u32_be(&ctx, rec->semantic_relation_type);
    write_u32_be(&ctx, rec->requirement_level);
    write_u32_be(&ctx, rec->effective_authority);
    write_u32_be(&ctx, rec->distinct_provenance_count);
    write_u32_be(&ctx, rec->conflict_membership);
    write_u32_be(&ctx, rec->candidate_priority_class);
    /* metric score key as int64 */
    int64_t key = rec->metric_score_key;
    uint8_t key_bytes[8];
    for (int i = 0; i < 8; i++)
        key_bytes[i] = (uint8_t)((key >> (56 - 8 * i)) & 0xFF);
    elpis_sha256_update(&ctx, key_bytes, 8);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

/* Lexicographic comparison of two candidate records per ranking rules. */
int elpis_bounded_view_candidate_cmp(
    const bounded_view_candidate_record *a,
    const bounded_view_candidate_record *b) {
    /* 1. Mandatory inclusion (mandatory before optional) */
    int a_mandatory = (a->candidate_priority_class <= CANDIDATE_PRIORITY_PROVENANCE);
    int b_mandatory = (b->candidate_priority_class <= CANDIDATE_PRIORITY_PROVENANCE);
    if (a_mandatory && !b_mandatory) return -1;
    if (!a_mandatory && b_mandatory) return 1;

    /* 2. Candidate priority class (lower numeric first) */
    if (a->candidate_priority_class != b->candidate_priority_class)
        return (int)a->candidate_priority_class - (int)b->candidate_priority_class;

    /* 3. Requirement level (lower = higher priority) */
    if (a->requirement_level != b->requirement_level)
        return (int)a->requirement_level - (int)b->requirement_level;

    /* 4. Origin class */
    if (a->origin_kind != b->origin_kind)
        return (int)a->origin_kind - (int)b->origin_kind;

    /* 5. Semantic graph hop (lower first) */
    if (a->graph_hop != b->graph_hop)
        return (int)a->graph_hop - (int)b->graph_hop;

    /* 6. Effective authority (higher first) */
    if (a->effective_authority != b->effective_authority)
        return (int)b->effective_authority - (int)a->effective_authority;

    /* 7. Distinct qualifying provenance count (higher first) */
    if (a->distinct_provenance_count != b->distinct_provenance_count)
        return (int)b->distinct_provenance_count - (int)a->distinct_provenance_count;

    /* 8. Conflict preservation flag (counterparts before unrelated) */
    if (a->conflict_membership != b->conflict_membership)
        return (int)b->conflict_membership - (int)a->conflict_membership;

    /* 9. Metric score key (higher first for similarity) */
    if (a->metric_score_key != b->metric_score_key)
        return (a->metric_score_key > b->metric_score_key) ? -1 : 1;

    /* 10. Semantic object digest (lexicographic) */
    int cmp = memcmp(&a->object_digest, &b->object_digest, HACF_DIGEST_BYTES);
    if (cmp != 0) return cmp;

    /* 11. Candidate record digest (lexicographic) */
    return memcmp(&a->candidate_record_digest, &b->candidate_record_digest,
                  HACF_DIGEST_BYTES);
}

int elpis_bounded_view_enumerate_candidates(
    const elpis_typed_evidence_view_v1                *typed_view,
    const elpis_semantic_bounded_view_seed_set_v1    *seed_set,
    const elpis_semantic_bounded_view_policy_v1      *policy,
    elpis_semantic_bounded_view_candidate_set_v1     *candidate_set)
{
    if (!typed_view || !seed_set || !policy || !candidate_set)
        return SEMANTIC_E_INVAL;

    elpis_bounded_view_candidate_set_init(candidate_set);

    memcpy(&candidate_set->typed_evidence_view_digest,
           &typed_view->typed_evidence_view_digest, HACF_DIGEST_BYTES);
    memcpy(&candidate_set->seed_set_digest,
           &seed_set->seed_set_digest, HACF_DIGEST_BYTES);
    memcpy(&candidate_set->bounded_view_policy_digest,
           &policy->policy_identity, HACF_DIGEST_BYTES);

    uint32_t cand_idx = 0;

    /* Each seed becomes a mandatory seed candidate */
    for (uint32_t i = 0; i < seed_set->seed_count &&
         cand_idx < BOUNDED_VIEW_MAX_CANDIDATES; i++) {
        const bounded_view_seed_record *seed = &seed_set->ordered_seeds[i];
        bounded_view_candidate_record *c = &candidate_set->ordered_candidates[cand_idx];
        c->object_kind = seed->semantic_object_kind;
        memcpy(&c->object_digest, &seed->semantic_object_digest, HACF_DIGEST_BYTES);
        c->origin_kind = CANDIDATE_ORIGIN_MANDATORY_SEED;
        memcpy(&c->origin_seed_digest, &seed->semantic_object_digest, HACF_DIGEST_BYTES);
        c->graph_hop = 0;
        c->semantic_relation_type = 0;
        c->requirement_level = seed->requirement_level;
        c->effective_authority = 0;
        c->distinct_provenance_count = 0;
        c->conflict_membership = (seed->seed_reason == SEED_REASON_CONFLICT_ANCHOR) ? 1 : 0;
        c->scope_membership = (seed->seed_reason == SEED_REASON_SCOPE_ANCHOR) ? 1 : 0;
        c->qualifier_membership = (seed->seed_reason == SEED_REASON_QUALIFIER_ANCHOR) ? 1 : 0;
        memset(&c->metric_profile_digest, 0, HACF_DIGEST_BYTES);
        c->metric_score_key = 0;
        c->candidate_priority_class =
            seed->mandatory_inclusion ? CANDIDATE_PRIORITY_MANDATORY
                                       : CANDIDATE_PRIORITY_SEMANTIC;
        elpis_bounded_view_candidate_record_digest(c, &c->candidate_record_digest);
        memset(c->reserved, 0, sizeof(c->reserved));
        cand_idx++;
    }

    /* Graph expansion: for each admitted relation in typed view, add neighbors
     * within max_graph_hops. */
    uint32_t max_hops = policy->maximum_graph_hops;
    for (uint32_t r = 0; r < typed_view->admitted_relation_count &&
         cand_idx < BOUNDED_VIEW_MAX_CANDIDATES; r++) {
        /* Check if any seed is a target of this relation */
        hacf_digest target = typed_view->admitted_relation_digests[r];
        /* Flip first byte to get target object digest */
        target.bytes[0] ^= 0x01;

        for (uint32_t s = 0; s < seed_set->seed_count; s++) {
            const bounded_view_seed_record *seed = &seed_set->ordered_seeds[s];
            if (memcmp(&target, &seed->semantic_object_digest,
                       HACF_DIGEST_BYTES) == 0) {
                /* This relation targets a seed — add neighbor at hop 1 */
                bounded_view_candidate_record *c =
                    &candidate_set->ordered_candidates[cand_idx];
                c->object_kind = SEMANTIC_OBJECT_KIND_NODE;
                memcpy(&c->object_digest,
                       &typed_view->admitted_relation_digests[r], HACF_DIGEST_BYTES);
                c->origin_kind = CANDIDATE_ORIGIN_SEMANTIC_GRAPH_NEIGHBOR;
                memcpy(&c->origin_seed_digest,
                       &seed->semantic_object_digest, HACF_DIGEST_BYTES);
                c->graph_hop = 1;
                c->semantic_relation_type = 0;
                c->requirement_level = PREFERRED;
                c->effective_authority = 0;
                c->distinct_provenance_count = 0;
                c->conflict_membership = 0;
                c->scope_membership = 0;
                c->qualifier_membership = 0;
                memset(&c->metric_profile_digest, 0, HACF_DIGEST_BYTES);
                c->metric_score_key = 0;
                c->candidate_priority_class = CANDIDATE_PRIORITY_SEMANTIC;
                elpis_bounded_view_candidate_record_digest(
                    c, &c->candidate_record_digest);
                memset(c->reserved, 0, sizeof(c->reserved));
                cand_idx++;
                break;
            }
        }
    }

    candidate_set->candidate_count = cand_idx;

    elpis_bounded_view_candidate_set_identity(candidate_set,
                                              &candidate_set->candidate_set_digest);
    return SEMANTIC_OK;
}

int elpis_bounded_view_candidate_set_identity(
    const elpis_semantic_bounded_view_candidate_set_v1 *set, hacf_digest *out) {
    if (!set || !out || set->abi_version != BOUNDED_VIEW_CANDIDATE_ABI_VERSION)
        return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, CANDIDATE_DOMAIN);
    uint32_t ver = set->abi_version;
    write_u32_be(&ctx, ver);
    elpis_sha256_update(&ctx, set->typed_evidence_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, set->seed_set_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, set->bounded_view_policy_digest.bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, set->candidate_count);
    for (uint32_t i = 0; i < set->candidate_count; i++) {
        const bounded_view_candidate_record *c = &set->ordered_candidates[i];
        elpis_sha256_update(&ctx, c->candidate_record_digest.bytes, HACF_DIGEST_BYTES);
    }
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_bounded_view_candidate_set_validate(
    const elpis_semantic_bounded_view_candidate_set_v1 *set) {
    if (!set) return SEMANTIC_E_INVAL;
    if (set->abi_version != BOUNDED_VIEW_CANDIDATE_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (set->candidate_count > BOUNDED_VIEW_MAX_CANDIDATES) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(set->reserved); i++) {
        if (set->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    return SEMANTIC_OK;
}

int elpis_write_bounded_view_candidate_set(const char *path,
    const elpis_semantic_bounded_view_candidate_set_v1 *set) {
    if (!path || !set) return SEMANTIC_E_INVAL;
    return (int)p5_simple_write(path, (const uint8_t *)set, sizeof(*set));
}

int elpis_read_bounded_view_candidate_set(const char *path,
    elpis_semantic_bounded_view_candidate_set_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;
    fseek(f, 0, SEEK_END); long sz = ftell(f);
    if (sz != (long)sizeof(*out)) { fclose(f); return SEMANTIC_E_IO; }
    fseek(f, 0, SEEK_SET); size_t rd = fread(out, 1, sizeof(*out), f);
    fclose(f); if (rd != sizeof(*out)) return SEMANTIC_E_IO;
    int rc = elpis_bounded_view_candidate_set_validate(out);
    if (rc != SEMANTIC_OK) return rc;
    hacf_digest computed;
    elpis_bounded_view_candidate_set_identity(out, &computed);
    if (memcmp(&computed, &out->candidate_set_digest, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_E_DIGEST;
    return SEMANTIC_OK;
}
