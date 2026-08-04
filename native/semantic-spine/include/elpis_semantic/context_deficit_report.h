/* elpis_semantic/context_deficit_report.h — Context deficit report.
 *
 * Binds evaluation results to the composed view, embedding collections,
 * requirement set, and deficit policy. Determines overall disposition.
 *
 * Identity domain: "elpis.semantic.context_deficit_report.v1"
 */
#ifndef ELPIS_SEMANTIC_CONTEXT_DEFICIT_REPORT_H
#define ELPIS_SEMANTIC_CONTEXT_DEFICIT_REPORT_H

#include "elpis_semantic/context_deficit.h"
#include "elpis_semantic/embedding_collection.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CONTEXT_DEFICIT_REPORT_ABI_VERSION  1u
#define CONTEXT_MAX_EMBEDDING_COLLECTIONS   16u

/* ──────────────────────────────────────────────────────────────────── */
/* Overall disposition                                                   */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum overall_disposition {
    DISP_CONTEXT_SUFFICIENT     = 1,
    DISP_RETRIEVAL_REQUIRED     = 2,
    DISP_REQUIREMENT_SET_INVALID = 3,
    DISP_EVALUATION_BLOCKED     = 4
} overall_disposition;

/* ──────────────────────────────────────────────────────────────────── */
/* Context deficit report                                                */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_context_deficit_report_v1 {
    uint32_t                                  abi_version;
    hacf_digest                               composed_view_digest;
    hacf_digest                               embedding_collection_digests[CONTEXT_MAX_EMBEDDING_COLLECTIONS];
    uint32_t                                  embedding_collection_count;
    hacf_digest                               requirement_set_digest;
    hacf_digest                               deficit_policy_digest;
    hacf_digest                               per_requirement_result_digests[CONTEXT_MAX_REQUIREMENTS];
    uint32_t                                  result_count;
    uint32_t                                  satisfied_count;
    uint32_t                                  mandatory_deficit_count;
    uint32_t                                  preferred_deficit_count;
    uint32_t                                  diagnostic_deficit_count;
    uint32_t                                  blocked_evaluation_count;
    uint32_t                                  overall_disposition;
    hacf_digest                               report_identity;
    hacf_digest                               hacf_package_digest;
    uint8_t                                   reserved[32];
} elpis_semantic_context_deficit_report_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Report operations                                                     */
/* ──────────────────────────────────────────────────────────────────── */

/* Zero-initialize a deficit report. Sets abi_version. */
void elpis_context_deficit_report_init(
    elpis_semantic_context_deficit_report_v1 *report);

/* Compute report identity. Domain: "elpis.semantic.context_deficit_report.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || composed_view_digest(32)
 *             || embedding_collection_count(4 BE)
 *             || for each embedding collection digest: digest(32)
 *             || requirement_set_digest(32)
 *             || deficit_policy_digest(32)
 *             || result_count(4 BE)
 *             || for each result digest: digest(32)
 *             || satisfied_count(4 BE)
 *             || mandatory_deficit_count(4 BE)
 *             || preferred_deficit_count(4 BE)
 *             || diagnostic_deficit_count(4 BE)
 *             || blocked_evaluation_count(4 BE)
 *             || overall_disposition(4 BE). */
int elpis_context_deficit_report_identity(
    const elpis_semantic_context_deficit_report_v1 *report, hacf_digest *out);

/* Determine overall disposition from results + policy.
 * CONTEXT_SUFFICIENT: zero unsatisfied mandatory, zero policy-triggering
 *   preferred, zero blocked, no unsatisfied external-context requirements.
 * RETRIEVAL_REQUIRED: at least one retrieval-triggering deficit,
 *   zero blocking evaluations.
 * REQUIREMENT_SET_INVALID: requirement-set validation failed.
 * EVALUATION_BLOCKED: required evaluator unavailable or structural mismatch.
 * Errors never produce CONTEXT_SUFFICIENT. */
int elpis_context_deficit_report_disposition(
    const elpis_semantic_requirement_result_v1 *results, uint32_t result_count,
    const elpis_semantic_context_requirement_set_v1 *requirement_set,
    const elpis_semantic_context_deficit_policy_v1 *policy,
    uint32_t *disposition_out);

/* Build a complete deficit report from evaluation results.
 * Caller must free *report_out on error. */
int elpis_context_deficit_report_build(
    const semantic_snapshot_view          *composed_view,
    const elpis_semantic_embedding_collection_v1 *embedding_collections,
    uint32_t                                     collection_count,
    const elpis_semantic_context_requirement_set_v1 *requirement_set,
    const elpis_semantic_context_deficit_policy_v1  *policy,
    const elpis_semantic_requirement_result_v1 *results,
    uint32_t result_count,
    elpis_semantic_context_deficit_report_v1 **report_out);

int elpis_write_deficit_report(const char *path,
                                const elpis_semantic_context_deficit_report_v1 *report);
int elpis_read_deficit_report(const char *path,
                               elpis_semantic_context_deficit_report_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
