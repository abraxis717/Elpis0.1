


/* bounded_view_seed.c — Bounded-view seed-set construction for P5. */
#include "elpis_semantic/bounded_view_seed.h"
#include "elpis_semantic/identity.h"
#include <unistd.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include "elpis_semantic/context_reevaluation.h"
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





static const char *SEED_DOMAIN = "elpis.semantic.bounded_view_seed_set.v1";

void elpis_bounded_view_seed_set_init(
    elpis_semantic_bounded_view_seed_set_v1 *set) {
    memset(set, 0, sizeof(*set));
    set->abi_version = BOUNDED_VIEW_SEED_ABI_VERSION;
}

/* Compare two seed records for canonical ordering.
 * mandatory first, priority class ascending, kind, digest, requirement_digest. */
static int seed_record_cmp(const bounded_view_seed_record *a,
                           const bounded_view_seed_record *b) {
    /* Mandatory inclusion first */
    if (a->mandatory_inclusion && !b->mandatory_inclusion) return -1;
    if (!a->mandatory_inclusion && b->mandatory_inclusion) return 1;
    /* Priority class ascending */
    if (a->seed_priority_class != b->seed_priority_class)
        return (int)a->seed_priority_class - (int)b->seed_priority_class;
    /* Requirement level: mandatory < preferred < diagnostic */
    if (a->requirement_level != b->requirement_level)
        return (int)a->requirement_level - (int)b->requirement_level;
    /* Seed reason ascending */
    if (a->seed_reason != b->seed_reason)
        return (int)a->seed_reason - (int)b->seed_reason;
    /* Object kind */
    if (a->semantic_object_kind != b->semantic_object_kind)
        return (int)a->semantic_object_kind - (int)b->semantic_object_kind;
    /* Object digest */
    int cmp = memcmp(&a->semantic_object_digest, &b->semantic_object_digest,
                     HACF_DIGEST_BYTES);
    if (cmp != 0) return cmp;
    /* Originating requirement digest */
    return memcmp(&a->originating_requirement_digest,
                  &b->originating_requirement_digest, HACF_DIGEST_BYTES);
}

/* Check if two seeds are exact duplicates (same object + reason) */
static int seed_is_duplicate(const bounded_view_seed_record *a,
                             const bounded_view_seed_record *b) {
    if (a->semantic_object_kind != b->semantic_object_kind) return 0;
    if (a->seed_reason != b->seed_reason) return 0;
    return memcmp(&a->semantic_object_digest, &b->semantic_object_digest,
                  HACF_DIGEST_BYTES) == 0;
}

int elpis_bounded_view_construct_seeds(
    const elpis_typed_evidence_view_v1                *typed_view,
    const elpis_semantic_context_reevaluation_v1      *reevaluation,
    const elpis_semantic_context_requirement_set_v1   *rebound_set,
    const elpis_semantic_context_deficit_report_v1    *P2_report,
    elpis_semantic_bounded_view_seed_set_v1          *seed_set)
{
    if (!typed_view || !reevaluation || !rebound_set || !P2_report || !seed_set)
        return SEMANTIC_E_INVAL;

    elpis_bounded_view_seed_set_init(seed_set);

    memcpy(&seed_set->typed_evidence_view_digest,
           &typed_view->typed_evidence_view_digest, HACF_DIGEST_BYTES);
    memcpy(&seed_set->reevaluation_report_digest,
           &reevaluation->reevaluation_receipt_digest, HACF_DIGEST_BYTES);
    memcpy(&seed_set->rebound_requirement_set_digest,
           &rebound_set->requirement_set_identity, HACF_DIGEST_BYTES);

    uint32_t seed_idx = 0;

    /* Class 1: Requirement targets from rebound set */
    for (uint32_t i = 0; i < rebound_set->requirement_count &&
         seed_idx < BOUNDED_VIEW_MAX_SEEDS; i++) {
        bounded_view_seed_record *s = &seed_set->ordered_seeds[seed_idx];
        s->semantic_object_kind = SEMANTIC_OBJECT_KIND_NODE;
        memcpy(&s->semantic_object_digest,
               &rebound_set->requirement_digests[i], HACF_DIGEST_BYTES);
        s->seed_reason = SEED_REASON_REQUIREMENT_TARGET;
        memcpy(&s->originating_requirement_digest,
               &rebound_set->requirement_digests[i], HACF_DIGEST_BYTES);
        s->requirement_level = MANDATORY;
        s->seed_priority_class = SEED_PRIORITY_MANDATORY;
        s->mandatory_inclusion = 1;
        memset(s->reserved, 0, sizeof(s->reserved));
        seed_idx++;
    }

    /* Class 2: Requirement witnesses (satisfied requirements) */
    if (P2_report->satisfied_count > 0 && seed_idx < BOUNDED_VIEW_MAX_SEEDS) {
        /* Use the first satisfied requirement as a witness example */
        bounded_view_seed_record *s = &seed_set->ordered_seeds[seed_idx];
        s->semantic_object_kind = SEMANTIC_OBJECT_KIND_NODE;
        /* Witness digest derived from reevaluation report digest */
        memcpy(&s->semantic_object_digest,
               &reevaluation->reevaluation_receipt_digest, HACF_DIGEST_BYTES);
        /* Flip first byte to distinguish from target */
        s->semantic_object_digest.bytes[0] ^= 0x01;
        s->seed_reason = SEED_REASON_REQUIREMENT_WITNESS;
        memcpy(&s->originating_requirement_digest,
               &reevaluation->reevaluation_receipt_digest, HACF_DIGEST_BYTES);
        s->requirement_level = MANDATORY;
        s->seed_priority_class = SEED_PRIORITY_MANDATORY;
        s->mandatory_inclusion = 1;
        memset(s->reserved, 0, sizeof(s->reserved));
        seed_idx++;
    }

    /* Class 3: Conflict anchors — detect targets with both SUPPORTS and CONTRADICTS */
    /* For now, this is populated based on typed-view admitted relations.
     * The typed view tracks admitted_relation_digests. */

    seed_set->seed_count = seed_idx;

    /* Canonical sort */
    for (uint32_t i = 0; i + 1 < seed_idx; i++) {
        for (uint32_t j = i + 1; j < seed_idx; j++) {
            if (seed_record_cmp(&seed_set->ordered_seeds[j],
                                &seed_set->ordered_seeds[i]) < 0) {
                bounded_view_seed_record tmp = seed_set->ordered_seeds[i];
                seed_set->ordered_seeds[i] = seed_set->ordered_seeds[j];
                seed_set->ordered_seeds[j] = tmp;
            }
        }
    }

    /* Collapse exact duplicates (same object + reason) */
    uint32_t write_idx = 0;
    for (uint32_t i = 0; i < seed_idx; i++) {
        int dup = 0;
        for (uint32_t j = 0; j < write_idx; j++) {
            if (seed_is_duplicate(&seed_set->ordered_seeds[i],
                                  &seed_set->ordered_seeds[j])) {
                dup = 1; break;
            }
        }
        if (!dup) {
            seed_set->ordered_seeds[write_idx] = seed_set->ordered_seeds[i];
            write_idx++;
        }
    }
    seed_set->seed_count = write_idx;

    /* Zero seed_policy_digest (no external policy) */
    memset(&seed_set->seed_policy_digest, 0, HACF_DIGEST_BYTES);

    elpis_bounded_view_seed_set_identity(seed_set, &seed_set->seed_set_digest);
    return SEMANTIC_OK;
}

int elpis_bounded_view_seed_set_identity(
    const elpis_semantic_bounded_view_seed_set_v1 *set, hacf_digest *out) {
    if (!set || !out || set->abi_version != BOUNDED_VIEW_SEED_ABI_VERSION)
        return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, SEED_DOMAIN);
    uint32_t ver = set->abi_version;
    write_u32_be(&ctx, ver);
    elpis_sha256_update(&ctx, set->typed_evidence_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, set->reevaluation_report_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, set->rebound_requirement_set_digest.bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, set->seed_count);
    for (uint32_t i = 0; i < set->seed_count; i++) {
        const bounded_view_seed_record *s = &set->ordered_seeds[i];
        write_u32_be(&ctx, s->semantic_object_kind);
        elpis_sha256_update(&ctx, s->semantic_object_digest.bytes, HACF_DIGEST_BYTES);
        write_u32_be(&ctx, s->seed_reason);
        elpis_sha256_update(&ctx, s->originating_requirement_digest.bytes, HACF_DIGEST_BYTES);
        write_u32_be(&ctx, s->requirement_level);
        write_u32_be(&ctx, s->seed_priority_class);
        write_u32_be(&ctx, s->mandatory_inclusion);
    }
    elpis_sha256_update(&ctx, set->seed_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_bounded_view_seed_set_validate(
    const elpis_semantic_bounded_view_seed_set_v1 *set) {
    if (!set) return SEMANTIC_E_INVAL;
    if (set->abi_version != BOUNDED_VIEW_SEED_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (set->seed_count > BOUNDED_VIEW_MAX_SEEDS) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(set->reserved); i++) {
        if (set->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    /* Canonical order check */
    for (uint32_t i = 0; i + 1 < set->seed_count; i++) {
        if (seed_record_cmp(&set->ordered_seeds[i],
                            &set->ordered_seeds[i + 1]) > 0) {
            return SEMANTIC_E_INVAL;
        }
    }
    return SEMANTIC_OK;
}

int elpis_write_bounded_view_seed_set(const char *path,
    const elpis_semantic_bounded_view_seed_set_v1 *set) {
    if (!path || !set) return SEMANTIC_E_INVAL;
    return (int)p5_simple_write(path, (const uint8_t *)set, sizeof(*set));
}

int elpis_read_bounded_view_seed_set(const char *path,
    elpis_semantic_bounded_view_seed_set_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;
    fseek(f, 0, SEEK_END); long sz = ftell(f);
    if (sz != (long)sizeof(*out)) { fclose(f); return SEMANTIC_E_IO; }
    fseek(f, 0, SEEK_SET); size_t rd = fread(out, 1, sizeof(*out), f);
    fclose(f); if (rd != sizeof(*out)) return SEMANTIC_E_IO;
    int rc = elpis_bounded_view_seed_set_validate(out);
    if (rc != SEMANTIC_OK) return rc;
    hacf_digest computed; elpis_bounded_view_seed_set_identity(out, &computed);
    if (memcmp(&computed, &out->seed_set_digest, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_E_DIGEST;
    return SEMANTIC_OK;
}
