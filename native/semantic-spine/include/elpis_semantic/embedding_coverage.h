/* elpis_semantic/embedding_coverage.h — Embedding coverage diagnostics.
 *
 * Deterministic diagnostics only. Does not make retrieval decisions.
 * Reports coverage statistics for a composed view and embedding profile.
 */
#ifndef ELPIS_SEMANTIC_EMBEDDING_COVERAGE_H
#define ELPIS_SEMANTIC_EMBEDDING_COVERAGE_H

#include "elpis_semantic/embedding_view.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────────────────────────────────────────────────────────── */
/* Coverage diagnostic report                                            */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct embedding_coverage_report {
    uint32_t    total_eligible_nodes;
    uint32_t    nodes_with_embedding;
    uint32_t    nodes_without_embedding;
    uint32_t    coverage_numerator;
    uint32_t    coverage_denominator;
    uint32_t    duplicate_vector_count;
    uint32_t    multi_profile_node_count;
    uint32_t    conflicting_reference_count;
    uint32_t    zero_norm_vector_count;

    /* Census arrays (parallel with counts) */
    uint32_t    authority_buckets[4];    /* by authority level 0-3 */
    uint32_t    authority_bucket_count;
    hacf_digest provenance_census[256]; /* up to 256 unique provenances */
    uint32_t    provenance_census_count;
    hacf_digest profile_census[256];    /* up to 256 unique profiles */
    uint32_t    profile_census_count;
} embedding_coverage_report;

/* ──────────────────────────────────────────────────────────────────── */
/* Coverage operations                                                   */
/* ──────────────────────────────────────────────────────────────────── */

/* Compute coverage diagnostics for a composed view and profile.
 * Returns SEMANTIC_OK or error. */
int elpis_embedding_coverage_compute(
    const embedding_composed_view *view,
    const elpis_semantic_embedding_profile_v1 *profile,
    embedding_coverage_report *out);

/* Get all embedding references from the view for coverage analysis.
 * Returns count placed in out (up to out_capacity). */
uint32_t embedding_composed_view_all_refs(
    const embedding_composed_view *view,
    const elpis_semantic_embedding_ref_v1 **out,
    uint32_t out_capacity);

#ifdef __cplusplus
}
#endif
#endif
