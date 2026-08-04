#ifndef ELPIS_SEMANTIC_TRM_ALIGNMENT_HANDOFF_H
#define ELPIS_SEMANTIC_TRM_ALIGNMENT_HANDOFF_H

#include <stdint.h>
#include "trm_alignment_report.h"

#define TRM_HANDOFF_DIGEST_LEN 64
#define TRM_HANDOFF_STATEMENT_LEN 512

typedef enum {
    TRM_HANDOFF_FROZEN_TRM_ALIGNMENT_DIAGNOSIS = 0,
} trm_handoff_kind_t;

typedef struct {
    uint32_t abi_version;
    trm_handoff_kind_t handoff_kind;
    char model_manifest_digest[TRM_HANDOFF_DIGEST_LEN];
    char native_contract_digest[TRM_HANDOFF_DIGEST_LEN];
    char alignment_policy_digest[TRM_HANDOFF_DIGEST_LEN];
    char p10_corpus_digest[TRM_HANDOFF_DIGEST_LEN];
    char diagnostic_fixture_manifest_digest[TRM_HANDOFF_DIGEST_LEN];
    char representation_results_digest[TRM_HANDOFF_DIGEST_LEN];
    char placement_results_digest[TRM_HANDOFF_DIGEST_LEN];
    char decoder_results_digest[TRM_HANDOFF_DIGEST_LEN];
    char guard_analysis_digest[TRM_HANDOFF_DIGEST_LEN];
    char recursive_shift_digest[TRM_HANDOFF_DIGEST_LEN];
    char native_control_digest[TRM_HANDOFF_DIGEST_LEN];
    char alignment_report_digest[TRM_HANDOFF_DIGEST_LEN];
    char diagnosis_verdict[TRM_DIAGNOSIS_LEN];
    char remediation_recommendation[TRM_DIAGNOSIS_LEN];
    char p10_negative_result_digest[TRM_HANDOFF_DIGEST_LEN];
    char projector_blocking_boundary_digest[TRM_HANDOFF_DIGEST_LEN];
    char handoff_digest[TRM_HANDOFF_DIGEST_LEN];
    char hacf_package_digest[TRM_HANDOFF_DIGEST_LEN];
    char p10r_statement[TRM_HANDOFF_STATEMENT_LEN];
    int p10_negative_result_unchanged;
    int frozen_model_unchanged;
    int no_weights_changed;
    int no_training;
    int runtime_admission;
} trm_alignment_handoff_t;

trm_alignment_handoff_t trm_alignment_handoff_create(void);
void trm_alignment_handoff_compute_digest(trm_alignment_handoff_t *handoff);
int trm_alignment_handoff_validate(const trm_alignment_handoff_t *handoff);

#endif
