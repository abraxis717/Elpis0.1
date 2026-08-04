/* elpis_semantic/trm_efficacy_report.h — Aggregate efficacy report v1.
 *
 * Final adjudication of frozen TRM guarded refinement efficacy.
 * Identity domain: "elpis.semantic.trm_efficacy_report.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_EFFICACY_REPORT_H
#define ELPIS_SEMANTIC_TRM_EFFICACY_REPORT_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_EFFICACY_REPORT_VERSION 1u

typedef enum trm_efficacy_verdict {
    TRM_VERDICT_STRUCTURALLY_EFFICACIOUS = 0u,
    TRM_VERDICT_STRUCTURALLY_MIXED = 1u,
    TRM_VERDICT_STRUCTURALLY_INEFFICACIOUS = 2u,
    TRM_VERDICT_EFFICACY_EVIDENCE_INVALID = 3u,
} trm_efficacy_verdict;

typedef struct elpis_semantic_trm_efficacy_report_v1 {
    uint32_t                          abi_version;

    /* Authority bindings */
    hacf_digest                       efficacy_policy_digest;
    hacf_digest                       evaluation_corpus_digest;
    hacf_digest                       reference_solution_manifest_digest;

    /* Aggregate counts */
    uint32_t                          total_initial_clues;
    uint32_t                          total_noop_correct_cells;
    uint32_t                          total_onestep_correct_cells;
    uint32_t                          total_bounded_correct_cells;
    uint32_t                          total_bounded_wrong_cells;

    int32_t                           aggregate_onestep_net_correct_gain;
    int32_t                           aggregate_bounded_net_correct_gain;

    uint32_t                          positive_fixture_count;
    uint32_t                          no_change_fixture_count;
    uint32_t                          negative_fixture_count;
    uint32_t                          wrong_final_state_count;
    uint32_t                          exactly_solved_count;

    /* Per-stratum improvement */
    uint32_t                          strata_improved[4];

    uint32_t                          total_model_invocations;
    uint32_t                          total_committed_steps;
    uint32_t                          total_rejected_steps;
    uint32_t                          total_candidate_changes;
    uint32_t                          total_admitted_changes;
    uint32_t                          total_correct_additions;
    uint32_t                          total_wrong_additions;
    uint32_t                          total_corrections;
    uint32_t                          total_regressions;
    uint32_t                          total_fixed_violation_attempts;
    uint32_t                          guard_rejection_count;
    uint32_t                          execution_failure_count;

    /* Verdict */
    uint32_t                          model_efficacy_verdict; /* trm_efficacy_verdict */

    /* Report digest */
    hacf_digest                       report_digest;

    uint8_t                           reserved[128];
} elpis_semantic_trm_efficacy_report_v1;

void elpis_trm_efficacy_report_init(
    elpis_semantic_trm_efficacy_report_v1 *report);

int elpis_trm_efficacy_report_identity(
    const elpis_semantic_trm_efficacy_report_v1 *report,
    hacf_digest *out);

int elpis_trm_efficacy_report_validate(
    const elpis_semantic_trm_efficacy_report_v1 *report);

int elpis_write_trm_efficacy_report(const char *path,
    const elpis_semantic_trm_efficacy_report_v1 *report);
int elpis_read_trm_efficacy_report(const char *path,
    elpis_semantic_trm_efficacy_report_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
