/* embedding_neighborhood.c — Bounded semantic-neighborhood views.
 *
 * Deterministic metric observation. Does not create semantic edges.
 * Does not mutate the hypergraph.
 */
#include "elpis_semantic/embedding_neighborhood.h"
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

/* ──────────────────────────────────────────────────────────────────── */
/* Internal: candidate entry for sorting                                 */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct candidate_entry {
    hacf_digest     node_digest;
    hacf_digest     ref_digest;
    hacf_digest     vector_digest;
    int64_t         score_key;
    double          raw_score;
    uint32_t       authority;
    hacf_digest     provenance_digest;
    int             is_distance; /* 1 = distance metric (lower is better) */
} candidate_entry;

/* Comparator for sorting candidates.
 * Similarity: higher score_key first, then smaller node digest, then smaller ref digest.
 * Distance: lower score_key first, then smaller node digest, then smaller ref digest. */
static int candidate_cmp(const void *pa, const void *pb) {
    const candidate_entry *a = (const candidate_entry *)pa;
    const candidate_entry *b = (const candidate_entry *)pb;

    int cmp_score;
    if (a->is_distance) {
        cmp_score = (a->score_key < b->score_key) ? -1 : (a->score_key > b->score_key) ? 1 : 0;
    } else {
        cmp_score = (a->score_key > b->score_key) ? -1 : (a->score_key < b->score_key) ? 1 : 0;
    }
    if (cmp_score != 0) return cmp_score;

    int cmp_node = memcmp(a->node_digest.bytes, b->node_digest.bytes, HACF_DIGEST_BYTES);
    if (cmp_node != 0) return cmp_node;

    return memcmp(a->ref_digest.bytes, b->ref_digest.bytes, HACF_DIGEST_BYTES);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Find vector bytes by vector digest                                    */
/* ──────────────────────────────────────────────────────────────────── */

static int find_vector_bytes(
    const elpis_semantic_embedding_vector_v1 *vectors, uint32_t vector_count,
    const uint8_t **vector_bytes,
    const hacf_digest *vector_digest,
    const uint8_t **out_bytes) {
    for (uint32_t i = 0; i < vector_count; i++) {
        if (memcmp(&vectors[i].vector_identity, vector_digest, sizeof(hacf_digest)) == 0 ||
            memcmp(&vectors[i].vector_bytes_digest, vector_digest, sizeof(hacf_digest)) == 0) {
            *out_bytes = vector_bytes[i];
            return 0;
        }
    }
    return -1;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Resolve neighborhood                                                  */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_resolve_neighborhood(
    const hacf_digest *composed_view_nodes, uint32_t composed_node_count,
    const elpis_semantic_embedding_ref_v1 *refs, uint32_t ref_count,
    const elpis_semantic_embedding_vector_v1 *vectors, uint32_t vector_count,
    const uint8_t **vector_bytes,
    const elpis_semantic_embedding_profile_v1 *profile,
    const embedding_neighborhood_query *query,
    elpis_semantic_embedding_neighborhood_v1 *out_neighborhood) {
    if (!composed_view_nodes || !refs || !vectors || !profile || !query || !out_neighborhood) return -1;
    memset(out_neighborhood, 0, sizeof(*out_neighborhood));
    out_neighborhood->abi_version = EMBEDDING_NEIGHBORHOOD_ABI_VERSION;
    memcpy(&out_neighborhood->query_vector_digest, &query->query_vector_digest, sizeof(hacf_digest));
    memcpy(&out_neighborhood->profile_digest, &query->profile_digest, sizeof(hacf_digest));
    memcpy(&out_neighborhood->neighborhood_policy_digest, &query->neighborhood_policy_digest, sizeof(hacf_digest));

    /* Find query vector bytes */
    const uint8_t *query_bytes = NULL;
    if (find_vector_bytes(vectors, vector_count, vector_bytes,
                          &query->query_vector_digest, &query_bytes) != 0) {
        /* Query vector must be found */
        return -1;
    }

    int is_distance = (profile->distance_metric == EMBEDDING_METRIC_SQUARED_L2);

    /* Collect all candidate entries */
    candidate_entry *candidates = calloc(ref_count, sizeof(candidate_entry));
    if (!candidates) return -2;
    uint32_t candidate_count = 0;

    for (uint32_t i = 0; i < ref_count; i++) {
        const elpis_semantic_embedding_ref_v1 *ref = &refs[i];

        /* Skip if not for the target profile */
        if (memcmp(&ref->embedding_profile_digest, &query->profile_digest, sizeof(hacf_digest)) != 0)
            continue;

        /* Authority filter */
        if (ref->authority < query->min_authority)
            continue;

        /* Provenance filter (all-zero = no filter) */
        static const uint8_t zero_digest[32] = {0};
        if (memcmp(&query->provenance_filter, zero_digest, sizeof(hacf_digest)) != 0) {
            if (memcmp(&ref->provenance_digest, &query->provenance_filter, sizeof(hacf_digest)) != 0)
                continue;
        }

        /* Compute score */
        const uint8_t *ref_bytes = NULL;
        if (find_vector_bytes(vectors, vector_count, vector_bytes,
                              &ref->embedding_vector_digest, &ref_bytes) != 0)
            continue;

        embedding_metric_result metric;
        if (elpis_embedding_compute_metric(profile, query_bytes, ref_bytes,
                                           profile->dimensions, &metric) != 0)
            continue;
        if (!metric.is_valid) continue;

        candidate_entry *c = &candidates[candidate_count++];
        memcpy(&c->node_digest, &ref->semantic_node_digest, sizeof(hacf_digest));
        memcpy(&c->ref_digest, &ref->ref_identity, sizeof(hacf_digest));
        memcpy(&c->vector_digest, &ref->embedding_vector_digest, sizeof(hacf_digest));
        c->score_key = metric.score_key;
        c->raw_score = metric.raw_score;
        c->authority = ref->authority;
        memcpy(&c->provenance_digest, &ref->provenance_digest, sizeof(hacf_digest));
        c->is_distance = is_distance;
    }

    /* Sort candidates */
    if (candidate_count > 0) {
        qsort(candidates, candidate_count, sizeof(candidate_entry), candidate_cmp);
    }

    /* Deduplicate nodes: retain highest-authority reference per node, then best score,
     * then lexicographically smallest reference digest. */
    typedef struct deduped_result {
        hacf_digest node_digest;
        candidate_entry entry;
    } deduped_result;

    deduped_result *deduped = calloc(candidate_count, sizeof(deduped_result));
    uint32_t deduped_count = 0;

    for (uint32_t i = 0; i < candidate_count; i++) {
        /* Check if this node already exists */
        int found = 0;
        for (uint32_t j = 0; j < deduped_count; j++) {
            if (memcmp(&deduped[j].node_digest, &candidates[i].node_digest, sizeof(hacf_digest)) == 0) {
                /* Already have this node — keep the best one (already sorted, first is best) */
                found = 1;
                break;
            }
        }
        if (!found) {
            memcpy(&deduped[deduped_count].node_digest, &candidates[i].node_digest, sizeof(hacf_digest));
            deduped[deduped_count].entry = candidates[i];
            deduped_count++;
        }
    }

    free(candidates);

    /* Apply offset and limit */
    uint32_t output_count = 0;
    if (query->offset < deduped_count) {
        uint32_t remaining = deduped_count - query->offset;
        uint32_t take = (remaining < query->limit) ? remaining : query->limit;
        for (uint32_t i = 0; i < take; i++) {
            uint32_t src = query->offset + i;
            embedding_neighborhood_entry *entry = &out_neighborhood->results[output_count];
            memcpy(&entry->semantic_node_digest, &deduped[src].node_digest, sizeof(hacf_digest));
            memcpy(&entry->embedding_ref_digest, &deduped[src].entry.ref_digest, sizeof(hacf_digest));
            memcpy(&entry->embedding_vector_digest, &deduped[src].entry.vector_digest, sizeof(hacf_digest));
            entry->score_key = deduped[src].entry.score_key;
            entry->raw_score = deduped[src].entry.raw_score;
            entry->authority = deduped[src].entry.authority;
            memcpy(&entry->provenance_digest, &deduped[src].entry.provenance_digest, sizeof(hacf_digest));
            entry->rank = (uint32_t)(output_count + 1);
            output_count++;
        }
    }
    out_neighborhood->result_count = output_count;

    /* Compute identity */
    elpis_embedding_neighborhood_identity(out_neighborhood, &out_neighborhood->neighborhood_identity);

    free(deduped);
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Neighborhood identity                                                 */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_neighborhood_identity(
    const elpis_semantic_embedding_neighborhood_v1 *nb, hacf_digest *out) {
    if (!nb || !out) return -1;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.embedding_neighborhood.v1");
    write_u32_be(&ctx, nb->abi_version);
    write_digest(&ctx, &nb->query_vector_digest);
    write_digest(&ctx, &nb->profile_digest);
    write_digest(&ctx, &nb->neighborhood_policy_digest);
    write_u32_be(&ctx, nb->collection_count);
    for (uint32_t i = 0; i < nb->collection_count; i++) {
        write_digest(&ctx, &nb->collection_identities[i]);
    }
    write_u32_be(&ctx, nb->result_count);
    for (uint32_t i = 0; i < nb->result_count; i++) {
        const embedding_neighborhood_entry *e = &nb->results[i];
        write_digest(&ctx, &e->semantic_node_digest);
        write_digest(&ctx, &e->embedding_ref_digest);
        write_digest(&ctx, &e->embedding_vector_digest);
        /* Score key as int64 */
        int64_t key = e->score_key;
        elpis_sha256_update(&ctx, &key, 8);
        write_digest(&ctx, &e->provenance_digest);
        write_u32_be(&ctx, e->rank);
    }
    elpis_sha256_final(&ctx, out->bytes);
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Validation                                                              */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_neighborhood_validate(const elpis_semantic_embedding_neighborhood_v1 *nb) {
    if (!nb) return -1;
    if (nb->abi_version != EMBEDDING_NEIGHBORHOOD_ABI_VERSION) return -1;
    if (nb->result_count > EMBEDDING_MAX_NEIGHBORHOOD_RESULTS) return -1;
    if (nb->collection_count > EMBEDDING_MAX_PROFILES) return -1;
    static const uint8_t zero_buf[64] = {0};
    if (memcmp(nb->reserved, zero_buf, sizeof(nb->reserved)) != 0) return -1;
    /* Verify ranks are sequential */
    for (uint32_t i = 0; i < nb->result_count; i++) {
        if (nb->results[i].rank != i + 1) return -1;
    }
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Lifecycle                                                               */
/* ──────────────────────────────────────────────────────────────────── */

elpis_semantic_embedding_neighborhood_v1 *elpis_embedding_neighborhood_create(void) {
    elpis_semantic_embedding_neighborhood_v1 *n = calloc(1, sizeof(*n));
    if (!n) return NULL;
    n->abi_version = EMBEDDING_NEIGHBORHOOD_ABI_VERSION;
    return n;
}

void elpis_embedding_neighborhood_destroy(elpis_semantic_embedding_neighborhood_v1 *nb) {
    free(nb);
}
