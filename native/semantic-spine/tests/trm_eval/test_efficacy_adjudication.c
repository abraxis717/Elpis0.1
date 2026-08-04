/* test_efficacy_adjudication.c — P10 efficacy adjudication tests. */
#include <stdio.h>
#include <string.h>
#include "elpis_semantic/trm_efficacy_policy.h"
#include "elpis_semantic/trm_efficacy_report.h"
#include "elpis_semantic/trm_delta_handoff.h"

static int tests_passed = 0;
static int tests_failed = 0;

#define CHECK(cond, msg) do { \
    if (!(cond)) { printf("FAIL: %s\n", msg); tests_failed++; } \
    else { tests_passed++; } \
} while(0)

int main(void) {
    /* Test policy init and validate */
    elpis_semantic_trm_efficacy_policy_v1 policy;
    elpis_trm_efficacy_policy_init(&policy);
    CHECK(policy.abi_version == TRM_EFFICACY_POLICY_VERSION, "policy init");
    CHECK(policy.fixture_count == 16, "fixture count = 16");
    CHECK(policy.clue_counts[0] == 24, "stratum 0 = 24");
    CHECK(policy.clue_counts[1] == 32, "stratum 1 = 32");
    CHECK(policy.clue_counts[2] == 40, "stratum 2 = 40");
    CHECK(policy.clue_counts[3] == 48, "stratum 3 = 48");
    CHECK(policy.minimum_positive_fixture_count == 8, "min positive = 8");
    CHECK(policy.maximum_negative_fixture_count == 0, "max negative = 0");
    CHECK(elpis_trm_efficacy_policy_validate(&policy) == 0, "policy validates");

    /* Test policy persistence */
    elpis_write_trm_efficacy_policy("/tmp/test_policy.bin", &policy);
    elpis_semantic_trm_efficacy_policy_v1 policy2;
    elpis_read_trm_efficacy_policy("/tmp/test_policy.bin", &policy2);
    CHECK(policy2.fixture_count == policy.fixture_count, "policy persistence");

    /* Test report init and validate */
    elpis_semantic_trm_efficacy_report_v1 report;
    elpis_trm_efficacy_report_init(&report);
    CHECK(report.abi_version == TRM_EFFICACY_REPORT_VERSION, "report init");
    CHECK(elpis_trm_efficacy_report_validate(&report) == 0, "report validates");

    report.model_efficacy_verdict = TRM_VERDICT_STRUCTURALLY_MIXED;
    CHECK(elpis_trm_efficacy_report_validate(&report) == 0, "mixed verdict validates");

    report.model_efficacy_verdict = 99;
    CHECK(elpis_trm_efficacy_report_validate(&report) != 0, "invalid verdict rejected");

    /* Test handoff init */
    elpis_semantic_trm_delta_handoff_v1 handoff;
    elpis_trm_delta_handoff_init(&handoff);
    CHECK(handoff.abi_version == TRM_DELTA_HANDOFF_VERSION, "handoff init");
    CHECK(handoff.handoff_kind == TRM_HANDOFF_GUARDED_TRM_STRUCTURAL_DELTA_EVIDENCE, "handoff kind");
    CHECK(handoff.no_residual81_definition == 1, "no residual81");
    CHECK(handoff.runtime_admission_false == 1, "runtime admission false");
    CHECK(elpis_trm_delta_handoff_validate(&handoff) == 0, "handoff validates");

    /* Test handoff persistence */
    elpis_write_trm_delta_handoff("/tmp/test_handoff.bin", &handoff);
    elpis_semantic_trm_delta_handoff_v1 handoff2;
    elpis_read_trm_delta_handoff("/tmp/test_handoff.bin", &handoff2);
    CHECK(handoff2.handoff_kind == handoff.handoff_kind, "handoff persistence");

    /* Test verdict enum values */
    CHECK(TRM_VERDICT_STRUCTURALLY_EFFICACIOUS == 0, "EFFICACIOUS = 0");
    CHECK(TRM_VERDICT_STRUCTURALLY_MIXED == 1, "MIXED = 1");
    CHECK(TRM_VERDICT_STRUCTURALLY_INEFFICACIOUS == 2, "INEFFICACIOUS = 2");
    CHECK(TRM_VERDICT_EFFICACY_EVIDENCE_INVALID == 3, "INVALID = 3");

    printf("Results: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
