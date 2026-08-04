/* elpis_semantic/evidence_admission_receipt.h — Admission receipt.
 *
 * Every admission decision produces an immutable receipt preserving the full
 * provenance path from candidate through source spans to P3 retrieval artifacts.
 *
 * Graph-edge provenance status must be preserved as UNAVAILABLE when that
 * is the P3 ruling. Do not include a fake zero digest and call it recovered
 * provenance. If a fixed digest field is structurally required, pair it with
 * an explicit availability enum and require the digest to be all zero only
 * when availability is UNAVAILABLE.
 *
 * Identity domain: "elpis.semantic.evidence_admission_receipt.v1"
 */
#ifndef ELPIS_SEMANTIC_EVIDENCE_ADMISSION_RECEIPT_H
#define ELPIS_SEMANTIC_EVIDENCE_ADMISSION_RECEIPT_H

#include "elpis/cascade.h"
#include "elpis_semantic/retrieval_item_attachment.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EVIDENCE_ADMISSION_RECEIPT_ABI_VERSION 1u

#define EVIDENCE_RECEIPT_MAX_SPANS     64u
#define EVIDENCE_RECEIPT_MAX_BUNDLES   16u
#define EVIDENCE_RECEIPT_MAX_ATTACHMENTS 64u

typedef struct elpis_evidence_admission_receipt_v1 {
    uint32_t                        abi_version;
    hacf_digest                     base_snapshot_digest;
    hacf_digest                     query_overlay_digest;
    hacf_digest                     retrieval_expansion_digest;
    hacf_digest                     retrieval_expanded_view_digest;
    hacf_digest                     typing_bundle_digest;
    hacf_digest                     typer_profile_digest;
    hacf_digest                     candidate_digest;
    hacf_digest                     admission_policy_digest;
    hacf_digest                     admission_decision_digest;
    hacf_digest                     semantic_object_digest;
    hacf_digest                     source_span_digests[EVIDENCE_RECEIPT_MAX_SPANS];
    uint32_t                        source_span_count;
    hacf_digest                     retrieval_bundle_package_digests[EVIDENCE_RECEIPT_MAX_BUNDLES];
    uint32_t                        retrieval_bundle_count;
    hacf_digest                     retrieval_item_attachment_digests[EVIDENCE_RECEIPT_MAX_ATTACHMENTS];
    uint32_t                        retrieval_item_attachment_count;
    graph_provenance_status         graph_edge_provenance_status;
    hacf_digest                     receipt_digest;
    hacf_digest                     HACF_package_digest;
    uint8_t                         reserved[32];
} elpis_evidence_admission_receipt_v1;

/* Zero-initialize and set abi_version */
void elpis_admission_receipt_init(elpis_evidence_admission_receipt_v1 *receipt);

/* Compute receipt identity.
 * Domain: "elpis.semantic.evidence_admission_receipt.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || base_snapshot_digest(32) || query_overlay_digest(32)
 *             || retrieval_expansion_digest(32) || retrieval_expanded_view_digest(32)
 *             || typing_bundle_digest(32) || typer_profile_digest(32)
 *             || candidate_digest(32) || admission_policy_digest(32)
 *             || admission_decision_digest(32) || semantic_object_digest(32)
 *             || source_span_count(4 BE) || for each span: digest(32)
 *             || retrieval_bundle_count(4 BE) || for each bundle: digest(32)
 *             || retrieval_item_attachment_count(4 BE) || for each attachment: digest(32)
 *             || graph_edge_provenance_status(4 BE) || HACF_package_digest(32). */
int elpis_admission_receipt_identity(const elpis_evidence_admission_receipt_v1 *receipt,
                                      hacf_digest *out);

/* Validate receipt: all required digests present, counts match, reserved zero. */
int elpis_admission_receipt_validate(const elpis_evidence_admission_receipt_v1 *receipt);

/* Verify graph-edge provenance: UNAVAILABLE status requires all-zero recovered digest */
int elpis_receipt_provenance_status_verify(const elpis_evidence_admission_receipt_v1 *receipt);

/* Compare receipts by identity */
int elpis_admission_receipt_cmp(const elpis_evidence_admission_receipt_v1 *a,
                                 const elpis_evidence_admission_receipt_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
