/* test_fixture_metrics.c — P10 fixture metrics tests. */
#include <stdio.h>
#include <string.h>
#include "elpis_semantic/trm_fixture_metrics.h"
#include "elpis_semantic/trm_step_metrics.h"

static int tests_passed = 0;
static int tests_failed = 0;

#define CHECK(cond, msg) do { \
    if (!(cond)) { printf("FAIL: %s\n", msg); tests_failed++; } \
    else { tests_passed++; } \
} while(0)

int main(void) {
    /* Test fixture metrics init */
    elpis_semantic_trm_fixture_metrics_v1 fm;
    elpis_trm_fixture_metrics_init(&fm);
    CHECK(fm.abi_version == TRM_FIXTURE_METRICS_VERSION, "fixture metrics init abi_version");

    /* Test validation */
    CHECK(elpis_trm_fixture_metrics_validate(&fm) == 0, "empty fixture metrics validates");

    /* Test step metrics init */
    elpis_semantic_trm_step_metrics_v1 sm;
    elpis_trm_step_metrics_init(&sm);
    CHECK(sm.abi_version == TRM_STEP_METRICS_VERSION, "step metrics init");
    CHECK(elpis_trm_step_metrics_validate(&sm) == 0, "step metrics validates");

    /* Test persistence round-trip for fixture metrics */
    fm.fixture_ordinal = 42;
    fm.clue_stratum = 32;
    fm.fixture_verdict = TRM_FIXTURE_POSITIVE_IMPROVEMENT;
    elpis_write_trm_fixture_metrics("/tmp/test_fm.bin", &fm);
    elpis_semantic_trm_fixture_metrics_v1 fm2;
    elpis_read_trm_fixture_metrics("/tmp/test_fm.bin", &fm2);
    CHECK(fm2.fixture_ordinal == fm.fixture_ordinal, "fm persistence ordinal");
    CHECK(fm2.clue_stratum == fm.clue_stratum, "fm persistence stratum");
    CHECK(fm2.fixture_verdict == fm.fixture_verdict, "fm persistence verdict");

    /* Test persistence round-trip for step metrics */
    sm.step_index = 5;
    sm.correct_additions = 2;
    sm.regressions = 1;
    elpis_write_trm_step_metrics("/tmp/test_sm.bin", &sm);
    elpis_semantic_trm_step_metrics_v1 sm2;
    elpis_read_trm_step_metrics("/tmp/test_sm.bin", &sm2);
    CHECK(sm2.step_index == sm.step_index, "sm persistence step_index");
    CHECK(sm2.correct_additions == sm.correct_additions, "sm persistence correct_additions");

    /* Test invalid version rejected */
    fm.abi_version = 0;
    CHECK(elpis_trm_fixture_metrics_validate(&fm) != 0, "invalid version rejected");

    printf("Results: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
