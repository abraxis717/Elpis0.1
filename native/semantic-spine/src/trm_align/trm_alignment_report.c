#include "elpis_semantic/trm_alignment_report.h"
#include <string.h>
#include <stdio.h>
#include <openssl/sha.h>

static void sha256_hex(const void *data, size_t len, char *out, size_t out_len) {
    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256(data, len, hash);
    for (int i = 0; i < SHA256_DIGEST_LENGTH && (size_t)(i * 2 + 2) < out_len; i++) {
        sprintf(out + i * 2, "%02x", hash[i]);
    }
}

trm_alignment_report_t trm_alignment_report_create(void) {
    trm_alignment_report_t report;
    memset(&report, 0, sizeof(report));
    report.abi_version = 1;
    strncpy(report.domain, "elpis.semantic.trm_alignment_report.v1", sizeof(report.domain) - 1);
    report.diagnosis_digest[0] = '\0';
    return report;
}

void trm_alignment_report_diagnose(trm_alignment_report_t *report,
                                    int rep_mismatch,
                                    int placement_mismatch,
                                    int decoder_mismatch,
                                    int guard_mismatch,
                                    int recursive_shift,
                                    int intrinsic_insufficiency,
                                    int clue_dist_mismatch,
                                    int task_dist_mismatch) {
    report->representation_mismatch = rep_mismatch;
    report->placement_mismatch = placement_mismatch;
    report->decoder_mismatch = decoder_mismatch;
    report->guard_granularity_mismatch = guard_mismatch;
    report->recursive_distribution_shift = recursive_shift;
    report->intrinsic_model_insufficiency = intrinsic_insufficiency;
    report->clue_distribution_mismatch = clue_dist_mismatch;
    report->task_distribution_mismatch = task_dist_mismatch;

    int confirmed_count = 0;
    if (rep_mismatch > 0) confirmed_count++;
    if (placement_mismatch > 0) confirmed_count++;
    if (decoder_mismatch > 0) confirmed_count++;
    if (guard_mismatch > 0) confirmed_count++;
    if (recursive_shift > 0) confirmed_count++;

    if (intrinsic_insufficiency > 0) {
        report->primary_diagnosis = TRM_DIAGNOSIS_INTRINSIC_MODEL_INSUFFICIENCY;
        report->remediation = TRM_REMEDIATION_RETIRE_FROZEN_TRM;
    } else if (confirmed_count >= 2) {
        report->primary_diagnosis = TRM_DIAGNOSIS_COMPOUND_ALIGNMENT_MISMATCH;
        report->remediation = TRM_REMEDIATION_COMPOUND_ALIGNMENT;
    } else if (rep_mismatch > 0) {
        report->primary_diagnosis = TRM_DIAGNOSIS_REPRESENTATION_MISMATCH;
        report->remediation = TRM_REMEDIATION_P8_INPUT_ADAPTER;
    } else if (placement_mismatch > 0) {
        report->primary_diagnosis = TRM_DIAGNOSIS_PLACEMENT_MISMATCH;
        report->remediation = TRM_REMEDIATION_P7_STRUCTURAL_PLACEMENT;
    } else if (decoder_mismatch > 0) {
        report->primary_diagnosis = TRM_DIAGNOSIS_DECODER_MISMATCH;
        report->remediation = TRM_REMEDIATION_P8_DECODER_SEMANTICS;
    } else if (guard_mismatch > 0) {
        report->primary_diagnosis = TRM_DIAGNOSIS_GUARD_GRANULARITY_MISMATCH;
        report->remediation = TRM_REMEDIATION_SEPARATE_PROPOSAL_GRANULARITY_GATE;
    } else if (recursive_shift > 0) {
        report->primary_diagnosis = TRM_DIAGNOSIS_RECURSIVE_DISTRIBUTION_SHIFT;
        report->remediation = TRM_REMEDIATION_P9_RECURSIVE_INPUT_POLICY;
    } else if (clue_dist_mismatch > 0 || task_dist_mismatch > 0) {
        report->primary_diagnosis = TRM_DIAGNOSIS_COMPOUND_ALIGNMENT_MISMATCH;
        report->remediation = TRM_REMEDIATION_RETIRE_FROZEN_TRM;
    } else {
        report->primary_diagnosis = TRM_DIAGNOSIS_ALIGNMENT_REVIEW_INCONCLUSIVE;
        report->remediation = TRM_REMEDIATION_COLLECT_MORE_EVIDENCE;
    }
}

void trm_alignment_report_compute_digest(trm_alignment_report_t *report) {
    if (!report) return;
    sha256_hex(report, sizeof(trm_alignment_report_t),
               report->diagnosis_digest, TRM_REPORT_DIGEST_LEN);
}

const char *trm_diagnosis_verdict_string(trm_diagnosis_verdict_t verdict) {
    switch (verdict) {
        case TRM_DIAGNOSIS_REPRESENTATION_MISMATCH: return "REPRESENTATION_MISMATCH_CONFIRMED";
        case TRM_DIAGNOSIS_PLACEMENT_MISMATCH: return "PLACEMENT_MISMATCH_CONFIRMED";
        case TRM_DIAGNOSIS_DECODER_MISMATCH: return "DECODER_MISMATCH_CONFIRMED";
        case TRM_DIAGNOSIS_GUARD_GRANULARITY_MISMATCH: return "GUARD_GRANULARITY_MISMATCH_CONFIRMED";
        case TRM_DIAGNOSIS_RECURSIVE_DISTRIBUTION_SHIFT: return "RECURSIVE_DISTRIBUTION_SHIFT_CONFIRMED";
        case TRM_DIAGNOSIS_COMPOUND_ALIGNMENT_MISMATCH: return "COMPOUND_ALIGNMENT_MISMATCH_CONFIRMED";
        case TRM_DIAGNOSIS_INTRINSIC_MODEL_INSUFFICIENCY: return "INTRINSIC_MODEL_INSUFFICIENCY_CONFIRMED";
        case TRM_DIAGNOSIS_ALIGNMENT_REVIEW_INCONCLUSIVE: return "ALIGNMENT_REVIEW_INCONCLUSIVE";
        case TRM_DIAGNOSIS_ALIGNMENT_EVIDENCE_INVALID: return "ALIGNMENT_EVIDENCE_INVALID";
        default: return "UNKNOWN";
    }
}

const char *trm_remediation_string(trm_remediation_recommendation_t rem) {
    switch (rem) {
        case TRM_REMEDIATION_P8_INPUT_ADAPTER: return "REMEDIATE_P8_INPUT_ADAPTER";
        case TRM_REMEDIATION_P7_STRUCTURAL_PLACEMENT: return "REMEDIATE_P7_STRUCTURAL_PLACEMENT";
        case TRM_REMEDIATION_P8_DECODER_SEMANTICS: return "REMEDIATE_P8_DECODER_SEMANTICS";
        case TRM_REMEDIATION_SEPARATE_PROPOSAL_GRANULARITY_GATE: return "DESIGN_SEPARATE_PROPOSAL_GRANULARITY_GATE";
        case TRM_REMEDIATION_P9_RECURSIVE_INPUT_POLICY: return "REMEDIATE_P9_RECURSIVE_INPUT_POLICY";
        case TRM_REMEDIATION_COMPOUND_ALIGNMENT: return "DESIGN_COMPOUND_ALIGNMENT_REMEDIATION";
        case TRM_REMEDIATION_RETIRE_FROZEN_TRM: return "RETIRE_FROZEN_TRM_FROM_REFINEMENT_ROLE";
        case TRM_REMEDIATION_COLLECT_MORE_EVIDENCE: return "COLLECT_MORE_ALIGNMENT_EVIDENCE";
        default: return "UNKNOWN";
    }
}
