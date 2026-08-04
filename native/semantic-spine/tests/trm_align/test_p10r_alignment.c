/* P10R alignment report test */
#include <stdio.h>
#include <assert.h>
#include "elpis_semantic/trm_alignment_report.h"
#include "elpis_semantic/trm_alignment_policy.h"
#include "elpis_semantic/trm_alignment_handoff.h"

int main(void) {
    /* Test report creation */
    trm_alignment_report_t report = trm_alignment_report_create();
    assert(report.abi_version == 1);

    /* Test diagnosis strings */
    assert(strcmp(trm_diagnosis_verdict_string(TRM_DIAGNOSIS_INTRINSIC_MODEL_INSUFFICIENCY),
                  "INTRINSIC_MODEL_INSUFFICIENCY_CONFIRMED") == 0);
    assert(strcmp(trm_diagnosis_verdict_string(TRM_DIAGNOSIS_COMPOUND_ALIGNMENT_MISMATCH),
                  "COMPOUND_ALIGNMENT_MISMATCH_CONFIRMED") == 0);
    assert(strcmp(trm_diagnosis_verdict_string(TRM_DIAGNOSIS_ALIGNMENT_REVIEW_INCONCLUSIVE),
                  "ALIGNMENT_REVIEW_INCONCLUSIVE") == 0);

    /* Test remediation strings */
    assert(strcmp(trm_remediation_string(TRM_REMEDIATION_RETIRE_FROZEN_TRM),
                  "RETIRE_FROZEN_TRM_FROM_REFINEMENT_ROLE") == 0);
    assert(strcmp(trm_remediation_string(TRM_REMEDIATION_COMPOUND_ALIGNMENT),
                  "DESIGN_COMPOUND_ALIGNMENT_REMEDIATION") == 0);

    /* Test intrinsic insufficiency diagnosis */
    trm_alignment_report_diagnose(&report, 0, 0, 0, 0, 0, 1, 0, 0);
    assert(report.primary_diagnosis == TRM_DIAGNOSIS_INTRINSIC_MODEL_INSUFFICIENCY);
    assert(report.remediation == TRM_REMEDIATION_RETIRE_FROZEN_TRM);
    assert(report.intrinsic_model_insufficiency == 1);

    /* Test compound mismatch */
    trm_alignment_report_t report2 = trm_alignment_report_create();
    trm_alignment_report_diagnose(&report2, 1, 1, 0, 0, 0, 0, 0, 0);
    assert(report2.primary_diagnosis == TRM_DIAGNOSIS_COMPOUND_ALIGNMENT_MISMATCH);
    assert(report2.remediation == TRM_REMEDIATION_COMPOUND_ALIGNMENT);

    /* Test single representation mismatch */
    trm_alignment_report_t report3 = trm_alignment_report_create();
    trm_alignment_report_diagnose(&report3, 1, 0, 0, 0, 0, 0, 0, 0);
    assert(report3.primary_diagnosis == TRM_DIAGNOSIS_REPRESENTATION_MISMATCH);
    assert(report3.remediation == TRM_REMEDIATION_P8_INPUT_ADAPTER);

    /* Test inconclusive when nothing confirmed */
    trm_alignment_report_t report4 = trm_alignment_report_create();
    trm_alignment_report_diagnose(&report4, 0, 0, 0, 0, 0, 0, 0, 0);
    assert(report4.primary_diagnosis == TRM_DIAGNOSIS_ALIGNMENT_REVIEW_INCONCLUSIVE);
    assert(report4.remediation == TRM_REMEDIATION_COLLECT_MORE_EVIDENCE);

    /* Test digest computation */
    trm_alignment_report_compute_digest(&report);
    assert(report.diagnosis_digest[0] != '\0');

    /* Test policy */
    trm_native_contract_t native = trm_native_contract_create();
    trm_alignment_policy_t policy = trm_alignment_policy_create(&native);
    assert(!trm_alignment_policy_is_sealed(&policy));
    assert(trm_alignment_policy_seal(&policy));
    assert(trm_alignment_policy_is_sealed(&policy));
    assert(trm_alignment_policy_validate(&policy));

    /* Test handoff */
    trm_alignment_handoff_t handoff = trm_alignment_handoff_create();
    assert(handoff.abi_version == 1);
    assert(handoff.handoff_kind == TRM_HANDOFF_FROZEN_TRM_ALIGNMENT_DIAGNOSIS);
    assert(handoff.runtime_admission == 0);
    assert(handoff.no_weights_changed == 1);
    assert(handoff.no_training == 1);
    assert(trm_alignment_handoff_validate(&handoff));
    trm_alignment_handoff_compute_digest(&handoff);
    assert(handoff.handoff_digest[0] != '\0');

    printf("PASS: test_alignment_report\n");
    return 0;
}
