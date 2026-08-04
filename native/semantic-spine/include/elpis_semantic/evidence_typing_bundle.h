/* elpis_semantic/evidence_typing_bundle.h — Evidence-typing proposal bundle.
 *
 * A typing bundle is the immutable container for all evidence-typer proposals
 * associated with one P3 retrieval expansion. P4 does not accept loose individual
 * proposals outside a verified typing bundle.
 *
 * Identity domain: "elpis.semantic.evidence_typing_bundle.v1"
 */
#ifndef ELPIS_SEMANTIC_EVIDENCE_TYPING_BUNDLE_H
#define ELPIS_SEMANTIC_EVIDENCE_TYPING_BUNDLE_H

#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EVIDENCE_TYPING_BUNDLE_ABI_VERSION 1u

#define EVIDENCE_BUNDLE_MAX_SPANS          256u
#define EVIDENCE_BUNDLE_MAX_CLAIMS         256u
#define EVIDENCE_BUNDLE_MAX_RELATIONS      256u

typedef struct elpis_evidence_typing_bundle_v1 {
    uint32_t        abi_version;
    hacf_digest     base_snapshot_digest;
    hacf_digest     query_overlay_digest;
    hacf_digest     retrieval_expansion_digest;
    hacf_digest     retrieval_expanded_view_digest;
    hacf_digest     typer_profile_digest;
    hacf_digest     evidence_span_digests[EVIDENCE_BUNDLE_MAX_SPANS];
    uint32_t        evidence_span_count;
    hacf_digest     claim_candidate_digests[EVIDENCE_BUNDLE_MAX_CLAIMS];
    uint32_t        claim_candidate_count;
    hacf_digest     relation_candidate_digests[EVIDENCE_BUNDLE_MAX_RELATIONS];
    uint32_t        relation_candidate_count;
    hacf_digest     typing_bundle_policy_digest;
    hacf_digest     typing_bundle_digest;
    hacf_digest     HACF_package_digest;
    uint8_t         reserved[32];
} elpis_evidence_typing_bundle_v1;

/* Zero-initialize and set abi_version */
void elpis_typing_bundle_init(elpis_evidence_typing_bundle_v1 *bundle);

/* Compute typing bundle identity.
 * Domain: "elpis.semantic.evidence_typing_bundle.v1"
 * Canonical ordering for spans: attachment_digest, byte_start, byte_end, span_digest
 * Canonical ordering for claims: claim_type, payload_digest, candidate_digest
 * Canonical ordering for relations: relation_type, target_digest, evidence_digest, candidate_digest
 *
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || base_snapshot_digest(32) || query_overlay_digest(32)
 *             || retrieval_expansion_digest(32) || retrieval_expanded_view_digest(32)
 *             || typer_profile_digest(32)
 *             || span_count(4 BE) || for each canonical span: digest(32)
 *             || claim_count(4 BE) || for each canonical claim: digest(32)
 *             || relation_count(4 BE) || for each canonical relation: digest(32)
 *             || typing_bundle_policy_digest(32)
 *             || HACF_package_digest(32). */
int elpis_typing_bundle_identity(const elpis_evidence_typing_bundle_v1 *bundle,
                                  hacf_digest *out);

/* Validate: exact base/overlay/expansion/expanded_view match P3, typer profile exists,
 * all spans belong to that retrieval expansion, all candidates reference only bundle spans,
 * all target objects exist, no candidate exceeds provider limits, counts bounded,
 * exact duplicate collapse, conflicting duplicate identities fail closed,
 * HACF package identity verifies, reserved zero. */
int elpis_typing_bundle_validate(const elpis_evidence_typing_bundle_v1 *bundle);

/* Compare bundles by identity */
int elpis_typing_bundle_cmp(const elpis_evidence_typing_bundle_v1 *a,
                             const elpis_evidence_typing_bundle_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
