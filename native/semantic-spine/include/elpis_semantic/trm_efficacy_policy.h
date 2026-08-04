/* elpis_semantic/trm_efficacy_policy.h — Pre-registered efficacy policy v1.
 *
 * Immutable policy that seals efficacy thresholds before corpus execution.
 * Identity domain: "elpis.semantic.trm_efficacy_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_EFFICACY_POLICY_H
#define ELPIS_SEMANTIC_TRM_EFFICACY_POLICY_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_EFFICACY_POLICY_VERSION 1u
#define TRM_EFFICACY_POLICY_FIXTURE_COUNT 16u
#define TRM_EFFICACY_POLICY_CLUE_STRATUM_COUNT 4u
#define TRM_EFFICACY_POLICY_FIXTURES_PER_STRATUM 4u
#define TRM_EFFICACY_POLICY_MAX_STEPS 16u

/* Clue stratum targets */
#define TRM_EFFICACY_POLICY_CLUE_COUNT_0 24u
#define TRM_EFFICACY_POLICY_CLUE_COUNT_1 32u
#define TRM_EFFICACY_POLICY_CLUE_COUNT_2 40u
#define TRM_EFFICACY_POLICY_CLUE_COUNT_3 48u

/* Efficacy thresholds */
#define TRM_EFFICACY_MIN_POSITIVE_FIXTURES 8u
#define TRM_EFFICACY_MAX_NEGATIVE_FIXTURES 0u
#define TRM_EFFICACY_MAX_WRONG_FINAL_CELLS 0u
#define TRM_EFFICACY_REQUIRE_STRATUM_IMPROVEMENT 1u
#define TRM_EFFICACY_REQUIRE_BOUNDED_NOT_WORSE 1u

typedef struct elpis_semantic_trm_efficacy_policy_v1 {
    uint32_t                          abi_version;

    /* Authority bindings */
    hacf_digest                       model_manifest_digest;
    hacf_digest                       runtime_policy_digest;
    hacf_digest                       refinement_policy_digest;

    /* Corpus configuration */
    uint32_t                          fixture_count;
    uint32_t                          clue_stratum_count;
    uint32_t                          fixtures_per_stratum;
    uint32_t                          clue_counts[TRM_EFFICACY_POLICY_CLUE_STRATUM_COUNT];

    /* Policy flags */
    uint32_t                          reference_solution_policy; /* EXACT_UNIQUE_SOLUTION=1 */
    uint32_t                          corpus_generation_policy; /* DETERMINISTIC_SHA256=1 */
    uint32_t                          baseline_policy;          /* NO_OP=1 */
    uint32_t                          one_step_policy;          /* ONE_GUARDED_STEP=1 */
    uint32_t                          bounded_policy;           /* QUALIFIED_P9_MAX_STEPS=1 */

    /* Efficacy thresholds */
    uint32_t                          minimum_positive_fixture_count;
    uint32_t                          maximum_negative_fixture_count;
    uint32_t                          maximum_wrong_final_cell_count;
    int32_t                           minimum_aggregate_net_correct_gain;
    uint32_t                          require_each_stratum_improvement;
    uint32_t                          require_bounded_not_worse_than_one_step;

    /* Policy seal */
    hacf_digest                       efficacy_policy_digest;

    uint8_t                           reserved[128];
} elpis_semantic_trm_efficacy_policy_v1;

void elpis_trm_efficacy_policy_init(
    elpis_semantic_trm_efficacy_policy_v1 *policy);

int elpis_trm_efficacy_policy_identity(
    const elpis_semantic_trm_efficacy_policy_v1 *policy,
    hacf_digest *out);

int elpis_trm_efficacy_policy_validate(
    const elpis_semantic_trm_efficacy_policy_v1 *policy);

int elpis_write_trm_efficacy_policy(const char *path,
    const elpis_semantic_trm_efficacy_policy_v1 *policy);
int elpis_read_trm_efficacy_policy(const char *path,
    elpis_semantic_trm_efficacy_policy_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
