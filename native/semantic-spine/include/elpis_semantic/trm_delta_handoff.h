/* elpis_semantic/trm_delta_handoff.h — P10 structural-delta handoff v1.
 *
 * Immutable downstream handoff containing all P10 delta evidence.
 * Identity domain: "elpis.semantic.trm_delta_handoff.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_DELTA_HANDOFF_H
#define ELPIS_SEMANTIC_TRM_DELTA_HANDOFF_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_DELTA_HANDOFF_VERSION 1u

typedef enum trm_handoff_kind {
    TRM_HANDOFF_GUARDED_TRM_STRUCTURAL_DELTA_EVIDENCE = 0u,
} trm_handoff_kind;

typedef struct elpis_semantic_trm_delta_handoff_v1 {
    uint32_t                          abi_version;
    uint32_t                          handoff_kind;

    /* Authority chain digests */
    hacf_digest                       model_manifest_digest;
    hacf_digest                       runtime_policy_digest;
    hacf_digest                       refinement_policy_digest;
    hacf_digest                       efficacy_policy_digest;
    hacf_digest                       evaluation_corpus_digest;
    hacf_digest                       reference_solution_manifest_digest;
    hacf_digest                       delta_corpus_digest;
    hacf_digest                       efficacy_report_digest;
    hacf_digest                       P9_witness_analysis_digest;
    hacf_digest                       semantic_trace_boundary_digest;
    hacf_digest                       projector_target_boundary_digest;
    hacf_digest                       handoff_policy_digest;

    /* HACF package */
    hacf_digest                       HACF_package_digest;

    /* Handoff identity */
    hacf_digest                       handoff_digest;

    /* Boundary statement */
    uint32_t                          benchmark_is_sudoku_structural;
    uint32_t                          no_semantic_correctness_claim;
    uint32_t                          categorical_deltas_preserve_from_to;
    uint32_t                          digit_subtraction_no_meaning;
    uint32_t                          candidate_admitted_committed_distinct;
    uint32_t                          projector_requires_separate_qualification;
    uint32_t                          no_residual81_definition;
    uint32_t                          no_host_direction;
    uint32_t                          runtime_admission_false;

    uint8_t                           reserved[128];
} elpis_semantic_trm_delta_handoff_v1;

void elpis_trm_delta_handoff_init(
    elpis_semantic_trm_delta_handoff_v1 *handoff);

int elpis_trm_delta_handoff_identity(
    const elpis_semantic_trm_delta_handoff_v1 *handoff,
    hacf_digest *out);

int elpis_trm_delta_handoff_validate(
    const elpis_semantic_trm_delta_handoff_v1 *handoff);

int elpis_write_trm_delta_handoff(const char *path,
    const elpis_semantic_trm_delta_handoff_v1 *handoff);
int elpis_read_trm_delta_handoff(const char *path,
    elpis_semantic_trm_delta_handoff_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
