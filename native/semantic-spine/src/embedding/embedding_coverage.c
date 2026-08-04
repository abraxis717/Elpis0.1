/* embedding_coverage.c — Embedding coverage diagnostics.
 *
 * Deterministic diagnostics only. Does not make retrieval decisions.
 */
#include "elpis_semantic/embedding_coverage.h"
#include <string.h>
#include <stdlib.h>

/* ──────────────────────────────────────────────────────────────────── */
/* All references helper                                                 */
/* ──────────────────────────────────────────────────────────────────── */

uint32_t embedding_composed_view_all_refs(
    const embedding_composed_view *view,
    const elpis_semantic_embedding_ref_v1 **out,
    uint32_t out_capacity) {
    if (!view || !view->refs) return 0;
    uint32_t take = (view->ref_count < out_capacity) ? view->ref_count : out_capacity;
    for (uint32_t i = 0; i < take; i++) {
        out[i] = &view->refs[i];
    }
    return take;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Coverage computation                                                  */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_embedding_coverage_compute(
    const embedding_composed_view *view,
    const elpis_semantic_embedding_profile_v1 *profile,
    embedding_coverage_report *out) {
    if (!view || !profile || !out) return -1;

    memset(out, 0, sizeof(*out));

    /* Get all references for the target profile */
    const elpis_semantic_embedding_ref_v1 *all_refs[4096];
    uint32_t total_refs = embedding_composed_view_all_refs(view, all_refs, 4096);

    /* Count nodes with/without embedding */
    typedef struct node_entry {
        hacf_digest digest;
        uint32_t    ref_count;
        int         has_profile_ref;
    } node_entry;

    node_entry *nodes = calloc(4096, sizeof(node_entry));
    if (!nodes) return -2;
    uint32_t node_count = 0;

    for (uint32_t i = 0; i < total_refs; i++) {
        const elpis_semantic_embedding_ref_v1 *ref = all_refs[i];

        /* Find or create node entry */
        int found = 0;
        for (uint32_t j = 0; j < node_count; j++) {
            if (memcmp(&nodes[j].digest, &ref->semantic_node_digest, sizeof(hacf_digest)) == 0) {
                nodes[j].ref_count++;
                if (memcmp(&ref->embedding_profile_digest, &profile->profile_identity, sizeof(hacf_digest)) == 0) {
                    nodes[j].has_profile_ref = 1;
                }
                found = 1;
                break;
            }
        }
        if (!found && node_count < 4096) {
            memcpy(&nodes[node_count].digest, &ref->semantic_node_digest, sizeof(hacf_digest));
            nodes[node_count].ref_count = 1;
            if (memcmp(&ref->embedding_profile_digest, &profile->profile_identity, sizeof(hacf_digest)) == 0) {
                nodes[node_count].has_profile_ref = 1;
            }
            node_count++;
        }
    }

    out->nodes_with_embedding = 0;
    out->nodes_without_embedding = 0;
    out->multi_profile_node_count = 0;
    out->conflicting_reference_count = 0;

    for (uint32_t i = 0; i < node_count; i++) {
        if (nodes[i].has_profile_ref) {
            out->nodes_with_embedding++;
        } else {
            out->nodes_without_embedding++;
        }
        if (nodes[i].ref_count > 1) {
            out->multi_profile_node_count++;
        }
    }

    /* Check for duplicate vectors and conflicts across all refs */
    for (uint32_t i = 0; i < total_refs; i++) {
        for (uint32_t j = i + 1; j < total_refs; j++) {
            /* Duplicate vector: same vector digest on different nodes */
            /* (This is allowed — same vector can be referenced by multiple nodes) */
            if (memcmp(&all_refs[i]->embedding_vector_digest, &all_refs[j]->embedding_vector_digest, sizeof(hacf_digest)) == 0 &&
                memcmp(&all_refs[i]->semantic_node_digest, &all_refs[j]->semantic_node_digest, sizeof(hacf_digest)) != 0) {
                out->duplicate_vector_count++;
            }
            /* Conflicting reference: same tuple, different vector */
            if (elpis_embedding_ref_is_conflict(all_refs[i], all_refs[j])) {
                out->conflicting_reference_count++;
            }
        }
    }

    /* Authority census */
    for (uint32_t i = 0; i < total_refs; i++) {
        uint32_t auth = all_refs[i]->authority;
        if (auth <= 3) {
            out->authority_buckets[auth]++;
        }
    }
    out->authority_bucket_count = 4;

    /* Provenance census (unique provenance digests) */
    for (uint32_t i = 0; i < total_refs; i++) {
        int found = 0;
        for (uint32_t j = 0; j < out->provenance_census_count; j++) {
            if (memcmp(&out->provenance_census[j], &all_refs[i]->provenance_digest, sizeof(hacf_digest)) == 0) {
                found = 1;
                break;
            }
        }
        if (!found && out->provenance_census_count < 256) {
            memcpy(&out->provenance_census[out->provenance_census_count],
                   &all_refs[i]->provenance_digest, sizeof(hacf_digest));
            out->provenance_census_count++;
        }
    }

    /* Profile census */
    for (uint32_t i = 0; i < total_refs; i++) {
        int found = 0;
        for (uint32_t j = 0; j < out->profile_census_count; j++) {
            if (memcmp(&out->profile_census[j], &all_refs[i]->embedding_profile_digest, sizeof(hacf_digest)) == 0) {
                found = 1;
                break;
            }
        }
        if (!found && out->profile_census_count < 256) {
            memcpy(&out->profile_census[out->profile_census_count],
                   &all_refs[i]->embedding_profile_digest, sizeof(hacf_digest));
            out->profile_census_count++;
        }
    }

    /* Coverage ratio */
    out->total_eligible_nodes = out->nodes_with_embedding + out->nodes_without_embedding;
    out->coverage_numerator = out->nodes_with_embedding;
    out->coverage_denominator = out->total_eligible_nodes;

    free(nodes);
    return 0;
}
