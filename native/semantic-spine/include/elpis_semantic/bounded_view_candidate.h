/* elpis_semantic/bounded_view_candidate.h — Bounded-view candidate enumeration.
 *
 * Candidates arise from explicit qualified structures only: mandatory seeds,
 * semantic graph neighbors, required participants, closures, and metric supplements.
 *
 * Identity domain: "elpis.semantic.bounded_view_candidate.v1"
 */
#ifndef ELPIS_SEMANTIC_BOUNDED_VIEW_CANDIDATE_H
#define ELPIS_SEMANTIC_BOUNDED_VIEW_CANDIDATE_H

#include "elpis_semantic/bounded_view_seed.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BOUNDED_VIEW_CANDIDATE_ABI_VERSION 1u
#define BOUNDED_VIEW_MAX_CANDIDATES        2048u

typedef enum bounded_view_candidate_origin {
    CANDIDATE_ORIGIN_MANDATORY_SEED        = 0,
    CANDIDATE_ORIGIN_SEMANTIC_GRAPH_NEIGHBOR = 1,
    CANDIDATE_ORIGIN_REQUIRED_PARTICIPANT  = 2,
    CANDIDATE_ORIGIN_SCOPE_CLOSURE         = 3,
    CANDIDATE_ORIGIN_QUALIFIER_CLOSURE     = 4,
    CANDIDATE_ORIGIN_CONFLICT_CLOSURE      = 5,
    CANDIDATE_ORIGIN_PROVENANCE_WITNESS    = 6,
    CANDIDATE_ORIGIN_TRANSPORT_WITNESS     = 7,
    CANDIDATE_ORIGIN_METRIC_SUPPLEMENT     = 8
} bounded_view_candidate_origin;

typedef enum bounded_view_candidate_priority {
    CANDIDATE_PRIORITY_MANDATORY   = 0,
    CANDIDATE_PRIORITY_CONFLICT    = 1,
    CANDIDATE_PRIORITY_PROVENANCE  = 2,
    CANDIDATE_PRIORITY_SEMANTIC    = 3,
    CANDIDATE_PRIORITY_METRIC      = 4,
    CANDIDATE_PRIORITY_OPTIONAL    = 5
} bounded_view_candidate_priority;

typedef struct bounded_view_candidate_record {
    semantic_asserted_object_kind object_kind;
    hacf_digest                   object_digest;
    uint32_t                      origin_kind;
    hacf_digest                   origin_seed_digest;
    uint32_t                      graph_hop;
    uint32_t                      semantic_relation_type;
    uint32_t                      requirement_level;
    uint32_t                      effective_authority;
    uint32_t                      distinct_provenance_count;
    uint32_t                      conflict_membership;
    uint32_t                      scope_membership;
    uint32_t                      qualifier_membership;
    hacf_digest                   metric_profile_digest;
    int64_t                       metric_score_key;
    uint32_t                      candidate_priority_class;
    hacf_digest                   candidate_record_digest;
    uint8_t                       reserved[32];
} bounded_view_candidate_record;

/* Forward declarations */
typedef struct elpis_semantic_bounded_view_policy_v1 elpis_semantic_bounded_view_policy_v1;

typedef struct elpis_semantic_bounded_view_candidate_set_v1 {
    uint32_t                       abi_version;
    hacf_digest                    typed_evidence_view_digest;
    hacf_digest                    seed_set_digest;
    hacf_digest                    bounded_view_policy_digest;
    bounded_view_candidate_record  ordered_candidates[BOUNDED_VIEW_MAX_CANDIDATES];
    uint32_t                       candidate_count;
    hacf_digest                    candidate_set_digest;
    uint8_t                        reserved[32];
} elpis_semantic_bounded_view_candidate_set_v1;

void elpis_bounded_view_candidate_set_init(
    elpis_semantic_bounded_view_candidate_set_v1 *set);

int elpis_bounded_view_enumerate_candidates(
    const elpis_typed_evidence_view_v1                *typed_view,
    const elpis_semantic_bounded_view_seed_set_v1    *seed_set,
    const elpis_semantic_bounded_view_policy_v1      *policy,
    elpis_semantic_bounded_view_candidate_set_v1     *candidate_set);

int elpis_bounded_view_candidate_set_identity(
    const elpis_semantic_bounded_view_candidate_set_v1 *set, hacf_digest *out);

int elpis_bounded_view_candidate_set_validate(
    const elpis_semantic_bounded_view_candidate_set_v1 *set);

int elpis_bounded_view_candidate_cmp(
    const bounded_view_candidate_record *a,
    const bounded_view_candidate_record *b);

int elpis_bounded_view_candidate_record_digest(
    const bounded_view_candidate_record *rec, hacf_digest *out);

int elpis_bounded_view_rank_candidates(
    elpis_semantic_bounded_view_candidate_set_v1 *candidate_set);

int elpis_write_bounded_view_candidate_set(const char *path,
    const elpis_semantic_bounded_view_candidate_set_v1 *set);
int elpis_read_bounded_view_candidate_set(const char *path,
    elpis_semantic_bounded_view_candidate_set_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
