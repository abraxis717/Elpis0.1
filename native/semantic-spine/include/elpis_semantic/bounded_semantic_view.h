/* elpis_semantic/bounded_semantic_view.h — Bounded semantic view.
 *
 * Four separate planes: semantic, provenance, metric, control.
 * Only produced when P2 disposition = CONTEXT_SUFFICIENT and
 * P5 outcome = CONTEXT_SUFFICIENT_AND_BOUNDED_VIEW_READY.
 *
 * Identity domain: "elpis.semantic.bounded_semantic_view.v1"
 */
#ifndef ELPIS_SEMANTIC_BOUNDED_SEMANTIC_VIEW_H
#define ELPIS_SEMANTIC_BOUNDED_SEMANTIC_VIEW_H

#include "elpis_semantic/bounded_view_seed.h"
#include "elpis_semantic/bounded_view_candidate.h"
#include "elpis_semantic/bounded_view_policy.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BOUNDED_SEMANTIC_VIEW_ABI_VERSION 1u
#define BOUNDED_VIEW_MAX_PLANE_DIGEST_ENTRIES 512u

typedef struct elpis_semantic_bounded_semantic_view_v1 {
    uint32_t     abi_version;
    hacf_digest  root_query_overlay_digest;
    hacf_digest  P4_typed_evidence_view_digest;
    hacf_digest  P5_reevaluation_receipt_digest;
    hacf_digest  P2_deficit_report_digest;
    hacf_digest  rebound_requirement_set_digest;
    hacf_digest  seed_set_digest;
    hacf_digest  bounded_view_policy_digest;

    /* Semantic plane */
    hacf_digest  ordered_semantic_node_digests[BOUNDED_VIEW_MAX_PLANE_DIGEST_ENTRIES];
    uint32_t     semantic_node_count;
    hacf_digest  ordered_semantic_hyperedge_digests[BOUNDED_VIEW_MAX_PLANE_DIGEST_ENTRIES];
    uint32_t     semantic_hyperedge_count;
    hacf_digest  ordered_incidence_digests[BOUNDED_VIEW_MAX_PLANE_DIGEST_ENTRIES];
    uint32_t     incidence_count;

    /* Provenance plane */
    hacf_digest  ordered_assertion_digests[BOUNDED_VIEW_MAX_PLANE_DIGEST_ENTRIES];
    uint32_t     assertion_count;
    hacf_digest  ordered_source_span_digests[BOUNDED_VIEW_MAX_PLANE_DIGEST_ENTRIES];
    uint32_t     source_span_count;
    hacf_digest  ordered_transport_reference_digests[BOUNDED_VIEW_MAX_PLANE_DIGEST_ENTRIES];
    uint32_t     transport_reference_count;

    /* Metric plane */
    hacf_digest  ordered_embedding_reference_digests[BOUNDED_VIEW_MAX_PLANE_DIGEST_ENTRIES];
    uint32_t     embedding_reference_count;
    hacf_digest  ordered_metric_observation_digests[BOUNDED_VIEW_MAX_PLANE_DIGEST_ENTRIES];
    uint32_t     metric_observation_count;

    /* Control plane */
    hacf_digest  ordered_inclusion_record_digests[BOUNDED_VIEW_MAX_PLANE_DIGEST_ENTRIES];
    uint32_t     inclusion_record_count;
    hacf_digest  ordered_omission_record_digests[BOUNDED_VIEW_MAX_PLANE_DIGEST_ENTRIES];
    uint32_t     omission_record_count;

    hacf_digest  semantic_plane_digest;
    hacf_digest  provenance_plane_digest;
    hacf_digest  metric_plane_digest;
    hacf_digest  control_plane_digest;
    hacf_digest  bounded_view_digest;
    hacf_digest  HACF_package_digest;
    uint8_t      reserved[64];
} elpis_semantic_bounded_semantic_view_v1;

/* Forward declarations */
typedef struct elpis_semantic_context_reevaluation_v1 elpis_semantic_context_reevaluation_v1;

void elpis_bounded_semantic_view_init(elpis_semantic_bounded_semantic_view_v1 *view);

int elpis_bounded_semantic_view_construct(
    const elpis_typed_evidence_view_v1                *typed_view,
    const elpis_semantic_bounded_view_seed_set_v1    *seed_set,
    const elpis_semantic_bounded_view_candidate_set_v1 *candidate_set,
    const elpis_semantic_bounded_view_policy_v1      *policy,
    const elpis_semantic_context_reevaluation_v1     *reevaluation,
    elpis_semantic_bounded_semantic_view_v1          *view);

int elpis_bounded_semantic_view_identity(
    const elpis_semantic_bounded_semantic_view_v1 *view, hacf_digest *out);

int elpis_bounded_semantic_view_validate(
    const elpis_semantic_bounded_semantic_view_v1 *view);

int elpis_write_bounded_semantic_view(const char *path,
    const elpis_semantic_bounded_semantic_view_v1 *view);
int elpis_read_bounded_semantic_view(const char *path,
    elpis_semantic_bounded_semantic_view_v1 *out);

/* Mandatory closure — declared here since it needs the full bounded_semantic_view type */
int elpis_bounded_view_compute_mandatory_closure(
    const elpis_typed_evidence_view_v1                *typed_view,
    const elpis_semantic_bounded_view_seed_set_v1    *seed_set,
    const elpis_semantic_bounded_view_candidate_set_v1 *candidate_set,
    const elpis_semantic_bounded_view_policy_v1      *policy,
    elpis_semantic_bounded_semantic_view_v1          *view);

#ifdef __cplusplus
}
#endif
#endif
