/* elpis_semantic/retrieval_requirement_bundle.h — Retrieval requirement bundle.
 *
 * Collects ordered retrieval requirements derived from a context-deficit report.
 * Requirements are sorted canonically and deduplicated per policy.
 *
 * If the report disposition is CONTEXT_SUFFICIENT, no bundle is emitted
 * (recommended P2 behavior).
 *
 * Identity domain: "elpis.semantic.retrieval_requirement_bundle.v1"
 */
#ifndef ELPIS_SEMANTIC_RETRIEVAL_REQUIREMENT_BUNDLE_H
#define ELPIS_SEMANTIC_RETRIEVAL_REQUIREMENT_BUNDLE_H

#include "elpis_semantic/retrieval_requirement.h"
#include "elpis_semantic/context_deficit_policy.h"
#include "elpis_semantic/context_deficit_report.h"
#include "elpis_semantic/context_requirement_set.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RETRIEVAL_BUNDLE_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Retrieval requirement bundle record                                   */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_retrieval_requirement_bundle_v1 {
    uint32_t                    abi_version;
    hacf_digest                 context_deficit_report_digest;
    hacf_digest                 composed_view_digest;
    hacf_digest                 query_overlay_digest;
    hacf_digest                 requirement_set_digest;
    hacf_digest                 deficit_policy_digest;
    hacf_digest                 retrieval_requirement_digests[CONTEXT_MAX_RETRIEVAL_REQUIREMENTS];
    uint32_t                    retrieval_count;
    hacf_digest                 bundle_policy_digest;
    hacf_digest                 bundle_identity;
    hacf_digest                 hacf_package_digest;
    uint8_t                     reserved[32];
} elpis_semantic_retrieval_requirement_bundle_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Bundle operations                                                     */
/* ──────────────────────────────────────────────────────────────────── */

/* Zero-initialize a retrieval bundle. Sets abi_version. */
void elpis_retrieval_bundle_init(
    elpis_semantic_retrieval_requirement_bundle_v1 *bundle);

/* Add a retrieval requirement digest to the bundle.
 * Duplicate digests are silently collapsed per DEDUP_EXACT_COLLAPSE policy.
 * Returns SEMANTIC_OK, SEMANTIC_E_INVAL (limit exceeded),
 * or SEMANTIC_E_DUPLICATE. */
int elpis_retrieval_bundle_add(
    elpis_semantic_retrieval_requirement_bundle_v1 *bundle,
    const hacf_digest *requirement_digest);

/* Compute bundle identity.
 * Domain: "elpis.semantic.retrieval_requirement_bundle.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || context_deficit_report_digest(32)
 *             || composed_view_digest(32)
 *             || query_overlay_digest(32)
 *             || requirement_set_digest(32)
 *             || deficit_policy_digest(32)
 *             || retrieval_count(4 BE)
 *             || for each retrieval requirement digest: digest(32)
 *             || bundle_policy_digest(32). */
int elpis_retrieval_requirement_bundle_identity(
    const elpis_semantic_retrieval_requirement_bundle_v1 *bundle, hacf_digest *out);

/* Validate bundle: known ABI, zero reserved, count <= max,
 * retrieval digests sorted, target digests non-zero. */
int elpis_retrieval_bundle_validate(
    const elpis_semantic_retrieval_requirement_bundle_v1 *bundle);

/* Sort retrieval digests into canonical order:
 * 1. higher priority key (descending) — not available here since we only have digests,
 *    so sort by digest ascending as proxy.
 * 2. retrieval identity digest ascending. */
int elpis_retrieval_bundle_canonicalize(
    elpis_semantic_retrieval_requirement_bundle_v1 *bundle);

/* Build a retrieval-requirement bundle from a deficit report + results.
 * Only produces a bundle if disposition != CONTEXT_SUFFICIENT.
 * Caller must free *bundle_out on success. Returns SEMANTIC_E_INVAL if
 * the disposition is CONTEXT_SUFFICIENT (no bundle emitted). */
int elpis_retrieval_bundle_from_report(
    const elpis_semantic_context_deficit_report_v1   *report,
    const elpis_semantic_requirement_result_v1       *results,
    uint32_t                                          result_count,
    const elpis_semantic_context_requirement_set_v1  *requirement_set,
    const elpis_semantic_context_deficit_policy_v1   *policy,
    elpis_semantic_retrieval_requirement_bundle_v1   **bundle_out);

int elpis_write_retrieval_bundle(const char *path,
                                  const elpis_semantic_retrieval_requirement_bundle_v1 *bundle);
int elpis_read_retrieval_bundle(const char *path,
                                 elpis_semantic_retrieval_requirement_bundle_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
