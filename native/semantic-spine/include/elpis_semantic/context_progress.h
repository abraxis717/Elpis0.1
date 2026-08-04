/* elpis_semantic/context_progress.h — Progress measurement for P5 iteration.
 *
 * Progress is measured semantically, not by retrieved byte count.
 *
 * Identity domain: "elpis.semantic.context_progress.v1"
 */
#ifndef ELPIS_SEMANTIC_CONTEXT_PROGRESS_H
#define ELPIS_SEMANTIC_CONTEXT_PROGRESS_H

#include "elpis/cascade.h"
#include "elpis_semantic/context_deficit.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CONTEXT_PROGRESS_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Progress disposition                                                  */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum context_progress_disposition {
    PROGRESS_MEASURABLE_PROGRESS              = 0,
    PROGRESS_NO_PROGRESS_IDENTICAL_VIEW       = 1,
    PROGRESS_NO_PROGRESS_IDENTICAL_REQUIREMENTS = 2,
    PROGRESS_NO_PROGRESS_IDENTICAL_DEFICITS   = 3,
    PROGRESS_NO_PROGRESS_NONCONTRIBUTING_EVIDENCE = 4,
    PROGRESS_FIRST_EVALUATED_ROUND            = 5,
    PROGRESS_EVALUATION_BLOCKED               = 6
} context_progress_disposition;

/* ──────────────────────────────────────────────────────────────────── */
/* Progress report                                                       */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_context_progress_v1 {
    uint32_t                abi_version;

    hacf_digest             previous_iteration_state_digest;
    hacf_digest             current_iteration_state_inputs_digest;

    hacf_digest             previous_typed_evidence_view_digest;
    hacf_digest             current_typed_evidence_view_digest;

    hacf_digest             previous_deficit_report_digest;
    hacf_digest             current_deficit_report_digest;

    hacf_digest             previous_retrieval_requirement_bundle_digest;
    hacf_digest             current_retrieval_requirement_bundle_digest;

    uint32_t                new_semantic_node_count;
    uint32_t                new_semantic_hyperedge_count;
    uint32_t                new_assertion_count;
    uint32_t                new_evidence_span_count;
    uint32_t                new_requirement_satisfaction_count;

    uint32_t                resolved_mandatory_deficit_count;
    uint32_t                new_mandatory_deficit_count;
    uint32_t                unchanged_mandatory_deficit_count;

    uint32_t                contributing_semantic_delta_count;
    uint32_t                stagnant_round_count;

    uint32_t                progress_disposition; /* context_progress_disposition */

    hacf_digest             progress_report_digest;

    uint8_t                 reserved[64];
} elpis_semantic_context_progress_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                            */
/* ──────────────────────────────────────────────────────────────────── */

/* Zero-initialize. Sets abi_version. */
void elpis_context_progress_init(elpis_semantic_context_progress_v1 *report);

/* Measure progress between two iteration rounds.
 *
 * Contributing semantic delta: a new node, hyperedge, or assertion that
 * is matched by at least one P2 requirement evaluation or changes one
 * exact requirement result.
 *
 * Non-contributing: more bytes, duplicate evidence, irrelevant claims,
 * different rank, repeated typed assertion with no result change.
 *
 * Returns SEMANTIC_OK on success. */
int elpis_context_measure_progress(
    const elpis_semantic_context_progress_v1 *previous_inputs,
    const elpis_semantic_context_progress_v1 *current_inputs,
    const elpis_semantic_requirement_result_v1 *previous_results,
    uint32_t previous_result_count,
    const elpis_semantic_requirement_result_v1 *current_results,
    uint32_t current_result_count,
    elpis_semantic_context_progress_v1 *report);

/* Compute progress report identity. Domain: "elpis.semantic.context_progress.v1" */
int elpis_context_progress_identity(
    const elpis_semantic_context_progress_v1 *report, hacf_digest *out);

/* Validate: known ABI, zero reserved, valid disposition. */
int elpis_context_progress_validate(
    const elpis_semantic_context_progress_v1 *report);

/* Persistence */
int elpis_write_context_progress(const char *path,
                                  const elpis_semantic_context_progress_v1 *report);
int elpis_read_context_progress(const char *path,
                                 elpis_semantic_context_progress_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
