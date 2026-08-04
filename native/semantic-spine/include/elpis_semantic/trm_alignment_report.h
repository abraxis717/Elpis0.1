#ifndef ELPIS_SEMANTIC_TRM_ALIGNMENT_REPORT_H
#define ELPIS_SEMANTIC_TRM_ALIGNMENT_REPORT_H

#include <stdint.h>
#include "trm_alignment_metrics.h"

#define TRM_REPORT_DIGEST_LEN 64
#define TRM_DIAGNOSIS_LEN 128

typedef enum {
    TRM_DIAGNOSIS_REPRESENTATION_MISMATCH = 0,
    TRM_DIAGNOSIS_PLACEMENT_MISMATCH = 1,
    TRM_DIAGNOSIS_DECODER_MISMATCH = 2,
    TRM_DIAGNOSIS_GUARD_GRANULARITY_MISMATCH = 3,
    TRM_DIAGNOSIS_RECURSIVE_DISTRIBUTION_SHIFT = 4,
    TRM_DIAGNOSIS_COMPOUND_ALIGNMENT_MISMATCH = 5,
    TRM_DIAGNOSIS_INTRINSIC_MODEL_INSUFFICIENCY = 6,
    TRM_DIAGNOSIS_ALIGNMENT_REVIEW_INCONCLUSIVE = 7,
    TRM_DIAGNOSIS_ALIGNMENT_EVIDENCE_INVALID = 8,
} trm_diagnosis_verdict_t;

typedef enum {
    TRM_REMEDIATION_P8_INPUT_ADAPTER = 0,
    TRM_REMEDIATION_P7_STRUCTURAL_PLACEMENT = 1,
    TRM_REMEDIATION_P8_DECODER_SEMANTICS = 2,
    TRM_REMEDIATION_SEPARATE_PROPOSAL_GRANULARITY_GATE = 3,
    TRM_REMEDIATION_P9_RECURSIVE_INPUT_POLICY = 4,
    TRM_REMEDIATION_COMPOUND_ALIGNMENT = 5,
    TRM_REMEDIATION_RETIRE_FROZEN_TRM = 6,
    TRM_REMEDIATION_COLLECT_MORE_EVIDENCE = 7,
} trm_remediation_recommendation_t;

typedef struct {
    uint32_t abi_version;
    char domain[64];
    trm_diagnosis_verdict_t primary_diagnosis;
    int representation_mismatch;   /* 0=REJECTED, 1=CONFIRMED, -1=INCONCLUSIVE */
    int placement_mismatch;
    int decoder_mismatch;
    int guard_granularity_mismatch;
    int recursive_distribution_shift;
    int intrinsic_model_insufficiency;
    int clue_distribution_mismatch;
    int task_distribution_mismatch;
    trm_remediation_recommendation_t remediation;
    char diagnosis_digest[TRM_REPORT_DIGEST_LEN];
} trm_alignment_report_t;

trm_alignment_report_t trm_alignment_report_create(void);
void trm_alignment_report_diagnose(trm_alignment_report_t *report,
                                    int rep_mismatch,
                                    int placement_mismatch,
                                    int decoder_mismatch,
                                    int guard_mismatch,
                                    int recursive_shift,
                                    int intrinsic_insufficiency,
                                    int clue_dist_mismatch,
                                    int task_dist_mismatch);
void trm_alignment_report_compute_digest(trm_alignment_report_t *report);
const char *trm_diagnosis_verdict_string(trm_diagnosis_verdict_t verdict);
const char *trm_remediation_string(trm_remediation_recommendation_t rem);

#endif
