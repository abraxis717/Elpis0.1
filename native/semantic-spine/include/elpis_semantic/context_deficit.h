/* elpis_semantic/context_deficit.h — Context deficit evaluator.
 *
 * Evaluates every requirement in a requirement set against the composed
 * semantic view + embedding collections. Produces per-requirement results
 * with deterministic ordering and deficit classification.
 *
 * Does NOT short-circuit after the first mandatory failure — full census.
 * Does NOT mutate inputs. Does NOT infer semantic truth.
 * Does NOT treat embedding proximity as semantic support.
 */
#ifndef ELPIS_SEMANTIC_CONTEXT_DEFICIT_H
#define ELPIS_SEMANTIC_CONTEXT_DEFICIT_H

#include "elpis_semantic/context_requirement.h"
#include "elpis_semantic/context_requirement_set.h"
#include "elpis_semantic/context_deficit_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/snapshot_view.h"
#include "elpis_semantic/embedding_collection.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CONTEXT_MAX_MATCHED_OBJECTS   64u
#define CONTEXT_MAX_MISSING_IDENTITIES 64u

/* ──────────────────────────────────────────────────────────────────── */
/* Evaluation status                                                     */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum evaluation_status {
    EVAL_STATUS_EVALUATED             = 1,
    EVAL_STATUS_BLOCKED_INVALID_REF   = 2,
    EVAL_STATUS_BLOCKED_UNSUPPORTED   = 3,
    EVAL_STATUS_BLOCKED_VIEW_MISMATCH = 4,
    EVAL_STATUS_BLOCKED_PROFILE_MISMATCH = 5,
    EVAL_STATUS_BLOCKED_INTERNAL      = 6
} evaluation_status;

/* ──────────────────────────────────────────────────────────────────── */
/* Satisfaction status                                                   */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum satisfaction_status {
    SAT_STATUS_SATISFIED    = 1,
    SAT_STATUS_UNSATISFIED  = 2,
    SAT_STATUS_NOT_EVALUATED = 3
} satisfaction_status;

/* ──────────────────────────────────────────────────────────────────── */
/* Per-requirement result                                                */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_requirement_result_v1 {
    hacf_digest                   requirement_digest;
    uint32_t                      evaluation_status;
    uint32_t                      satisfaction_status;
    uint32_t                      observed_count;
    uint32_t                      required_threshold;
    hacf_digest                   matched_object_digests[CONTEXT_MAX_MATCHED_OBJECTS];
    uint32_t                      matched_count;
    hacf_digest                   missing_identities[CONTEXT_MAX_MISSING_IDENTITIES];
    uint32_t                      missing_count;
    uint32_t                      deficit_reason;
    hacf_digest                   diagnostic_digest;
    uint8_t                       reserved[32];
} elpis_semantic_requirement_result_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Evaluator                                                             */
/* ──────────────────────────────────────────────────────────────────── */

/* Zero-initialize a requirement result. */
void elpis_requirement_result_init(elpis_semantic_requirement_result_v1 *result);

/* Compute diagnostic digest for a result (deterministic from all fields
 * except diagnostic_digest itself). */
int elpis_requirement_result_diagnostic(
    const elpis_semantic_requirement_result_v1 *result, hacf_digest *out);

/* Evaluate all requirements in the set against the composed view and
 * embedding collections. Results are ordered canonically by requirement
 * identity digest.
 *
 * Returns SEMANTIC_OK on success. The caller owns the results array and
 * must free it. *result_count_out <= requirement_set->requirement_count.
 *
 * Does NOT mutate: view, embedding_collections, requirement_set, policy. */
int elpis_context_evaluate_requirements(
    const semantic_snapshot_view          *composed_view,
    const elpis_semantic_embedding_collection_v1 *embedding_collections,
    uint32_t                                    collection_count,
    const elpis_semantic_context_requirement_set_v1 *requirement_set,
    const elpis_semantic_context_deficit_policy_v1  *policy,
    elpis_semantic_requirement_result_v1 **results_out,
    uint32_t                              *result_count_out);

/* Sort results canonically by requirement digest (ascending). */
void elpis_requirement_results_canonicalize(
    elpis_semantic_requirement_result_v1 *results, uint32_t count);

/* Compare two results by requirement digest (ascending). */
int elpis_requirement_result_cmp(
    const elpis_semantic_requirement_result_v1 *a,
    const elpis_semantic_requirement_result_v1 *b);

/* Count deficits by level from results. */
void elpis_count_deficits(
    const elpis_semantic_requirement_result_v1 *results, uint32_t count,
    const elpis_semantic_context_requirement_set_v1 *requirement_set,
    uint32_t *satisfied_out,
    uint32_t *mandatory_deficit_out,
    uint32_t *preferred_deficit_out,
    uint32_t *diagnostic_deficit_out,
    uint32_t *blocked_out);

#ifdef __cplusplus
}
#endif
#endif
