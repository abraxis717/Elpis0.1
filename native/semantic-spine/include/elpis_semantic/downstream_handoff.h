/* elpis_semantic/downstream_handoff.h — Downstream handoff ABI for P5.
 *
 * Sole P5 artifact intended for a future semantic topology compiler.
 * Not a Grid81 packet. Not a TRM input. Not a host direction.
 *
 * Identity domain: "elpis.semantic.downstream_handoff.v1"
 */
#ifndef ELPIS_SEMANTIC_DOWNSTREAM_HANDOFF_H
#define ELPIS_SEMANTIC_DOWNSTREAM_HANDOFF_H

#include "elpis_semantic/bounded_semantic_view.h"
#include "elpis_semantic/context_reevaluation.h"
#include "elpis_semantic/typed_evidence_view.h"
#include "elpis_semantic/context_deficit_report.h"
#include "elpis_semantic/context_requirement_set.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define DOWNSTREAM_HANDOFF_ABI_VERSION 1u
#define HANDOFF_MAX_PAYLOAD_REFERENCES 256u

/* ──────────────────────────────────────────────────────────────────── */
/* Handoff kind                                                          */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum downstream_handoff_kind {
    HANDOFF_KIND_SEMANTIC_TOPOLOGY_COMPILER_INPUT = 0
} downstream_handoff_kind;

/* ──────────────────────────────────────────────────────────────────── */
/* Feature schema record — node                                          */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct handoff_node_feature_v1 {
    hacf_digest             node_digest;
    uint32_t                numeric_node_type;
    uint32_t                semantic_flags;
    uint32_t                effective_authority;
    uint32_t                assertion_count;
    uint32_t                distinct_provenance_count;
    uint32_t                query_anchor_flag;
    uint32_t                requirement_target_flag;
    uint32_t                requirement_witness_flag;
    uint32_t                conflict_target_flag;
    uint32_t                scope_flag;
    uint32_t                qualifier_flag;
    uint32_t                embedding_availability;
    uint32_t                selected_source_span_count;
    uint32_t                inclusion_reason_bits;
    uint8_t                 reserved[32];
} handoff_node_feature_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Feature schema record — hyperedge                                     */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct handoff_hyperedge_feature_v1 {
    hacf_digest             hyperedge_digest;
    uint32_t                numeric_relation_type;
    uint32_t                semantic_flags;
    uint32_t                effective_authority;
    uint32_t                assertion_count;
    uint32_t                distinct_provenance_count;
    uint32_t                participant_count;
    uint32_t                conflict_polarity_class;
    uint32_t                requirement_witness_flag;
    uint32_t                transport_versus_semantic_class;
    uint32_t                inclusion_reason_bits;
    uint8_t                 reserved[32];
} handoff_hyperedge_feature_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Feature schema record — metric                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct handoff_metric_feature_v1 {
    hacf_digest             source_node_digest;
    hacf_digest             neighbor_node_digest;
    hacf_digest             embedding_profile_digest;
    int64_t                 integer_score_key;
    uint32_t                metric_kind;
    hacf_digest             neighborhood_view_digest;
    uint8_t                 reserved[32];
} handoff_metric_feature_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Payload dependency manifest                                           */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct handoff_payload_dependency_manifest_v1 {
    uint32_t                abi_version;
    hacf_digest             semantic_payload_digests[HANDOFF_MAX_PAYLOAD_REFERENCES];
    uint32_t                semantic_payload_count;
    hacf_digest             claim_payload_digests[HANDOFF_MAX_PAYLOAD_REFERENCES];
    uint32_t                claim_payload_count;
    hacf_digest             scope_payload_digests[HANDOFF_MAX_PAYLOAD_REFERENCES];
    uint32_t                scope_payload_count;
    hacf_digest             qualifier_payload_digests[HANDOFF_MAX_PAYLOAD_REFERENCES];
    uint32_t                qualifier_payload_count;
    hacf_digest             source_document_digests[HANDOFF_MAX_PAYLOAD_REFERENCES];
    uint32_t                source_document_count;
    hacf_digest             embedding_vector_digests[HANDOFF_MAX_PAYLOAD_REFERENCES];
    uint32_t                embedding_vector_count;
    hacf_digest             type_registry_manifest_digest;
    hacf_digest             authority_registry_manifest_digest;
    hacf_digest             manifest_digest;
    uint8_t                 reserved[32];
} handoff_payload_dependency_manifest_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Downstream handoff packet                                             */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_downstream_handoff_v1 {
    uint32_t                abi_version;

    uint32_t                handoff_kind; /* downstream_handoff_kind */

    hacf_digest             root_query_overlay_digest;
    hacf_digest             bounded_semantic_view_digest;

    hacf_digest             semantic_plane_digest;
    hacf_digest             provenance_plane_digest;
    hacf_digest             metric_plane_digest;
    hacf_digest             control_plane_digest;

    hacf_digest             type_registry_chain_digest;
    hacf_digest             authority_registry_digest;
    hacf_digest             requirement_set_digest;
    hacf_digest             context_report_digest;
    hacf_digest             bounded_view_policy_digest;

    hacf_digest             payload_dependency_manifest_digest;
    hacf_digest             feature_schema_digest;
    hacf_digest             handoff_policy_digest;

    hacf_digest             handoff_digest;
    hacf_digest             HACF_package_digest;

    uint8_t                 reserved[64];
} elpis_semantic_downstream_handoff_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                            */
/* ──────────────────────────────────────────────────────────────────── */

/* Zero-initialize. Sets abi_version. */
void elpis_downstream_handoff_init(
    elpis_semantic_downstream_handoff_v1 *handoff);

/* Construct downstream handoff from bounded semantic view.
 * Binds all four plane digests, registry chain, authority registry,
 * requirement set, context report, and payload dependency manifest.
 * Returns SEMANTIC_OK on success. */
int elpis_downstream_handoff_construct(
    const elpis_semantic_bounded_semantic_view_v1 *bounded_view,
    const elpis_semantic_context_reevaluation_v1  *reevaluation,
    const elpis_semantic_context_requirement_set_v1 *rebound_set,
    const elpis_semantic_context_deficit_report_v1 *P2_report,
    elpis_semantic_downstream_handoff_v1          *handoff);

/* Compute handoff identity. Domain: "elpis.semantic.downstream_handoff.v1" */
int elpis_downstream_handoff_identity(
    const elpis_semantic_downstream_handoff_v1 *handoff, hacf_digest *out);

/* Validate: known ABI, zero reserved, valid handoff kind,
 * non-zero required digests, no Grid81/TRM coupling. */
int elpis_downstream_handoff_validate(
    const elpis_semantic_downstream_handoff_v1 *handoff);

/* Compute payload dependency manifest digest. */
int elpis_handoff_payload_manifest_identity(
    const handoff_payload_dependency_manifest_v1 *manifest, hacf_digest *out);

/* Persistence */
int elpis_write_downstream_handoff(const char *path,
                                    const elpis_semantic_downstream_handoff_v1 *handoff);
int elpis_read_downstream_handoff(const char *path,
                                   elpis_semantic_downstream_handoff_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
