/* elpis_semantic/evidence_admission.h — Immutable evidence-admission layer.
 *
 * The admission layer binds every decision (including rejections) and forms
 * an immutable layer over the P3 retrieval-expanded view. Does not mutate
 * base snapshot, query overlay, retrieval expansion, RetrievalBundles,
 * retrieval attachments, or typing bundle.
 *
 * Identity domain: "elpis.semantic.evidence_admission.v1"
 */
#ifndef ELPIS_SEMANTIC_EVIDENCE_ADMISSION_H
#define ELPIS_SEMANTIC_EVIDENCE_ADMISSION_H

#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EVIDENCE_ADMISSION_ABI_VERSION 1u

#define EVIDENCE_ADMISSION_MAX_DECISIONS  512u
#define EVIDENCE_ADMISSION_MAX_RECEIPTS   512u

typedef struct elpis_evidence_admission_v1 {
    uint32_t        abi_version;
    hacf_digest     base_snapshot_digest;
    hacf_digest     query_overlay_digest;
    hacf_digest     retrieval_expansion_digest;
    hacf_digest     retrieval_expanded_view_digest;
    hacf_digest     typing_bundle_digest;
    hacf_digest     admission_policy_digest;
    hacf_digest     admission_decision_digests[EVIDENCE_ADMISSION_MAX_DECISIONS];
    uint32_t        admission_decision_count;
    hacf_digest     admission_receipt_digests[EVIDENCE_ADMISSION_MAX_RECEIPTS];
    uint32_t        admission_receipt_count;
    hacf_digest     admission_segment_digest;
    uint32_t        admitted_claim_count;
    uint32_t        admitted_relation_count;
    uint32_t        rejected_claim_count;
    uint32_t        rejected_relation_count;
    hacf_digest     admission_layer_digest;
    hacf_digest     HACF_package_digest;
    uint8_t         reserved[32];
} elpis_evidence_admission_v1;

/* Zero-initialize and set abi_version */
void elpis_evidence_admission_init(elpis_evidence_admission_v1 *admission);

/* Compute admission layer identity.
 * Domain: "elpis.semantic.evidence_admission.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || base_snapshot_digest(32) || query_overlay_digest(32)
 *             || retrieval_expansion_digest(32) || retrieval_expanded_view_digest(32)
 *             || typing_bundle_digest(32) || admission_policy_digest(32)
 *             || admission_decision_count(4 BE) || for each: digest(32)
 *             || admission_receipt_count(4 BE) || for each: digest(32)
 *             || admission_segment_digest(32)
 *             || admitted_claim_count(4 BE) || admitted_relation_count(4 BE)
 *             || rejected_claim_count(4 BE) || rejected_relation_count(4 BE)
 *             || HACF_package_digest(32). */
int elpis_evidence_admission_identity(const elpis_evidence_admission_v1 *admission,
                                       hacf_digest *out);

/* Validate admission layer: all digests present, counts consistent, reserved zero. */
int elpis_evidence_admission_validate(const elpis_evidence_admission_v1 *admission);

/* Compare admission layers by identity */
int elpis_evidence_admission_cmp(const elpis_evidence_admission_v1 *a,
                                  const elpis_evidence_admission_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
