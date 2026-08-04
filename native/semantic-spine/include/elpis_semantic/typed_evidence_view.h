/* elpis_semantic/typed_evidence_view.h — Typed-evidence read-only view.
 *
 * Composes P0 base semantic snapshot, P0 query overlay, P1 embedding collections,
 * P3 retrieval expansion, and P4 evidence-admission layer into a unified
 * read-only view consumable by later context evaluation and projection stages.
 *
 * Identity domain: "elpis.semantic.typed_evidence_view.v1"
 */
#ifndef ELPIS_SEMANTIC_TYPED_EVIDENCE_VIEW_H
#define ELPIS_SEMANTIC_TYPED_EVIDENCE_VIEW_H

#include "elpis/cascade.h"
#include "elpis_semantic/evidence_admission_decision.h"
#include "elpis_semantic/evidence_relation_candidate.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TYPED_EVIDENCE_VIEW_ABI_VERSION 1u

#define TYPED_VIEW_MAX_EMBEDDING_COLLECTIONS 16u
#define TYPED_VIEW_MAX_CLAIMS          1024u
#define TYPED_VIEW_MAX_RELATIONS       1024u
#define TYPED_VIEW_MAX_ASSERTIONS      2048u
#define TYPED_VIEW_MAX_SPANS           2048u

/* Filter criteria for typed view queries */
typedef struct typed_view_filter {
    evidence_relation_type  relation_type;    /* 0 = any */
    uint32_t                source_authority; /* 0 = any */
    uint32_t                effective_authority; /* 0 = any */
    hacf_digest             typer_profile_digest; /* all-zero = any */
    hacf_digest             retrieval_bundle_digest; /* all-zero = any */
    hacf_digest             source_document_digest; /* all-zero = any */
} typed_view_filter;

/* Pagination state */
typedef struct typed_view_page {
    uint32_t    offset;
    uint32_t    limit;
    uint32_t    returned_count;
    uint32_t    has_more;
} typed_view_page;

/* Typed-evidence view — opaque handle; readers use accessor functions */
typedef struct elpis_typed_evidence_view elpis_typed_evidence_view;

typedef struct elpis_typed_evidence_view_v1 {
    uint32_t                abi_version;
    hacf_digest             base_snapshot_digest;
    hacf_digest             query_overlay_digest;
    hacf_digest             embedding_collection_digests[TYPED_VIEW_MAX_EMBEDDING_COLLECTIONS];
    uint32_t                embedding_collection_count;
    hacf_digest             retrieval_expansion_digest;
    hacf_digest             admission_layer_digest;
    hacf_digest             view_policy_digest;

    /* Index into admitted objects — digests only, not full objects */
    hacf_digest             admitted_claim_digests[TYPED_VIEW_MAX_CLAIMS];
    uint32_t                admitted_claim_count;
    hacf_digest             admitted_relation_digests[TYPED_VIEW_MAX_RELATIONS];
    uint32_t                admitted_relation_count;

    /* Source span index */
    hacf_digest             source_span_digests[TYPED_VIEW_MAX_SPANS];
    uint32_t                source_span_count;

    hacf_digest             typed_evidence_view_digest;
    uint8_t                 reserved[32];
} elpis_typed_evidence_view_v1;

/* Zero-initialize and set abi_version */
void elpis_typed_evidence_view_init(elpis_typed_evidence_view_v1 *view);

/* Compute typed-view identity.
 * Domain: "elpis.semantic.typed_evidence_view.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || base_snapshot_digest(32) || query_overlay_digest(32)
 *             || embedding_collection_count(4 BE) || for each: digest(32)
 *             || retrieval_expansion_digest(32) || admission_layer_digest(32)
 *             || view_policy_digest(32)
 *             || admitted_claim_count(4 BE) || for each claim: digest(32)
 *             || admitted_relation_count(4 BE) || for each relation: digest(32)
 *             || source_span_count(4 BE) || for each span: digest(32). */
int elpis_typed_evidence_view_identity(const elpis_typed_evidence_view_v1 *view,
                                        hacf_digest *out);

/* Validate typed-view fields */
int elpis_typed_evidence_view_validate(const elpis_typed_evidence_view_v1 *view);

/* ── View operations (read-only) ── */

/* Lookup admitted claim by digest — returns 0 if found, SEMANTIC_E_NOTFOUND otherwise */
int elpis_typed_view_lookup_claim(const elpis_typed_evidence_view_v1 *view,
                                   const hacf_digest *claim_digest,
                                   uint32_t *index_out);

/* Get assertion count for an admitted claim */
uint32_t elpis_typed_view_assertion_count_for_claim(const elpis_typed_evidence_view_v1 *view,
                                                     uint32_t claim_index);

/* Lookup admitted relation by digest */
int elpis_typed_view_lookup_relation(const elpis_typed_evidence_view_v1 *view,
                                      const hacf_digest *relation_digest,
                                      uint32_t *index_out);

/* Enumerate claims extracted from one evidence item */
uint32_t elpis_typed_view_claims_for_item(const elpis_typed_evidence_view_v1 *view,
                                           const hacf_digest *item_digest,
                                           uint32_t *claim_indices, uint32_t max_indices);

/* Enumerate relations targeting one semantic object */
uint32_t elpis_typed_view_relations_for_target(const elpis_typed_evidence_view_v1 *view,
                                                const hacf_digest *target_digest,
                                                uint32_t *relation_indices, uint32_t max_indices);

/* Enumerate SUPPORTS relations for a target */
uint32_t elpis_typed_view_supports_for_target(const elpis_typed_evidence_view_v1 *view,
                                               const hacf_digest *target_digest,
                                               uint32_t *relation_indices, uint32_t max_indices);

/* Enumerate CONTRADICTS relations for a target */
uint32_t elpis_typed_view_contradicts_for_target(const elpis_typed_evidence_view_v1 *view,
                                                  const hacf_digest *target_digest,
                                                  uint32_t *relation_indices, uint32_t max_indices);

/* Filter admitted relations by criteria with pagination */
uint32_t elpis_typed_view_filter_relations(const elpis_typed_evidence_view_v1 *view,
                                            const typed_view_filter *filter,
                                            const typed_view_page *page,
                                            uint32_t *relation_indices, uint32_t max_indices);

/* Filter admitted claims by criteria */
uint32_t elpis_typed_view_filter_claims(const elpis_typed_evidence_view_v1 *view,
                                         const typed_view_filter *filter,
                                         const typed_view_page *page,
                                         uint32_t *claim_indices, uint32_t max_indices);

/* Compare views by identity */
int elpis_typed_evidence_view_cmp(const elpis_typed_evidence_view_v1 *a,
                                   const elpis_typed_evidence_view_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
