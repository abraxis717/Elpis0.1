#ifndef ELPIS_SEMANTIC_TRM_ALIGNMENT_POLICY_H
#define ELPIS_SEMANTIC_TRM_ALIGNMENT_POLICY_H

#include <stdint.h>
#include "trm_native_contract.h"

#define TRM_ALIGNMENT_POLICY_ABI_VERSION 1
#define TRM_ALIGNMENT_POLICY_DOMAIN "elpis.semantic.trm_alignment_policy.v1"
#define TRM_HYPOTHESIS_MAX 16
#define TRM_LANE_MAX 8
#define TRM_LANE_ID_LEN 64
#define TRM_DIGEST_LEN 64
#define TRM_OBSERVATION_LEN 256

typedef enum {
    TRM_HYPOTHESIS_INPUT_REPRESENTATION_MISMATCH = 0,
    TRM_HYPOTHESIS_BLANK_OR_CLASS_ORDER_MISMATCH = 1,
    TRM_HYPOTHESIS_LAYOUT_DTYPE_OR_NORMALIZATION_MISMATCH = 2,
    TRM_HYPOTHESIS_P7_PLACEMENT_MISMATCH = 3,
    TRM_HYPOTHESIS_CLUE_DISTRIBUTION_MISMATCH = 4,
    TRM_HYPOTHESIS_DECODER_SEMANTICS_MISMATCH = 5,
    TRM_HYPOTHESIS_ATOMIC_GUARD_GRANULARITY_MISMATCH = 6,
    TRM_HYPOTHESIS_RECURSIVE_STATE_DISTRIBUTION_SHIFT = 7,
    TRM_HYPOTHESIS_COMPOUND_MISMATCH = 8,
    TRM_HYPOTHESIS_INTRINSIC_MODEL_INSUFFICIENCY = 9,
} trm_hypothesis_id_t;

typedef struct {
    trm_hypothesis_id_t id;
    char supporting_observation[TRM_OBSERVATION_LEN];
    char contradicting_observation[TRM_OBSERVATION_LEN];
    char control_lane[TRM_LANE_ID_LEN];
    char comparison_lane[TRM_LANE_ID_LEN];
    char decision_threshold[TRM_OBSERVATION_LEN];
    char confidence_rule[TRM_OBSERVATION_LEN];
} trm_hypothesis_t;

typedef struct {
    uint32_t abi_version;
    char model_manifest_digest[TRM_DIGEST_LEN];
    char p8_adapter_policy_digest[TRM_DIGEST_LEN];
    char p9_refinement_policy_digest[TRM_DIGEST_LEN];
    char p10_corpus_digest[TRM_DIGEST_LEN];
    char native_contract_digest[TRM_DIGEST_LEN];
    char enabled_representation_lanes[TRM_LANE_MAX][TRM_LANE_ID_LEN];
    uint32_t representation_lane_count;
    char enabled_placement_lanes[TRM_LANE_MAX][TRM_LANE_ID_LEN];
    uint32_t placement_lane_count;
    char enabled_decoder_analyses[TRM_LANE_MAX][TRM_LANE_ID_LEN];
    uint32_t decoder_analysis_count;
    char enabled_guard_analyses[TRM_LANE_MAX][TRM_LANE_ID_LEN];
    uint32_t guard_analysis_count;
    char enabled_recursive_shift_analyses[TRM_LANE_MAX][TRM_LANE_ID_LEN];
    uint32_t recursive_shift_count;
    uint32_t fixture_count_per_control;
    uint32_t maximum_model_invocations_per_fixture;
    char comparison_metric_registry_digest[TRM_DIGEST_LEN];
    char diagnosis_rule_digest[TRM_DIGEST_LEN];
    char alignment_policy_digest[TRM_DIGEST_LEN];
    trm_hypothesis_t hypotheses[TRM_HYPOTHESIS_MAX];
    uint32_t hypothesis_count;
    int sealed;
} trm_alignment_policy_t;

trm_alignment_policy_t trm_alignment_policy_create(const trm_native_contract_t *native);
int trm_alignment_policy_seal(trm_alignment_policy_t *policy);
int trm_alignment_policy_is_sealed(const trm_alignment_policy_t *policy);
int trm_alignment_policy_validate(const trm_alignment_policy_t *policy);
void trm_alignment_policy_compute_digest(trm_alignment_policy_t *policy);
int trm_alignment_policy_add_hypothesis(trm_alignment_policy_t *policy, trm_hypothesis_t h);

#endif
