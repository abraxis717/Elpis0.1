/* elpis_semantic/refiner_bakeoff_policy.h — Immutable P11 bakeoff policy v1.
 *
 * Identity domain: "elpis.semantic.refiner_bakeoff_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINER_BAKEOFF_POLICY_H
#define ELPIS_SEMANTIC_REFINER_BAKEOFF_POLICY_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINER_BAKEOFF_POLICY_VERSION 1u
#define REFINER_MAX_CANDIDATES 8u

/* ──────────────────────────────────────────────────────────────────── */
/* One-step policy                                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum refiner_one_step_policy {
    REFINER_ONE_STEP_SINGLE_INVOCATION = 0u,
} refiner_one_step_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* Bounded policy                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_refiner_bounded_policy_v1 {
    uint32_t                          maximum_steps;
    uint32_t                          state_guard_enabled;
    uint32_t                          termination_on_cycle;
    uint32_t                          termination_on_no_change;
    uint32_t                          termination_on_complete_board;
    uint32_t                          termination_on_guard_rejection;
    uint32_t                          failure_retains_last_committed;
} elpis_semantic_refiner_bounded_policy_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Failure policy                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum refiner_failure_policy {
    REFINER_FAILURE_RETAIN_LAST_COMMITTED = 0u,
} refiner_failure_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* Timeout policy                                                         */
/* ──────────────────────────────────────────────────────────────────── */

#define REFINER_DEFAULT_TIMEOUT_SECONDS 300u

/* ──────────────────────────────────────────────────────────────────── */
/* Bakeoff policy                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_refiner_bakeoff_policy_v1 {
    uint32_t                          abi_version;

    /* P10/P8/P9 bindings */
    hacf_digest                       P10_corpus_digest;
    hacf_digest                       P10_efficacy_policy_digest;
    hacf_digest                       P8_guard_policy_digest;
    hacf_digest                       P9_refinement_policy_digest;

    /* Enabled candidates (manifest digests) */
    uint32_t                          enabled_candidate_count;
    hacf_digest                       enabled_candidate_digests[REFINER_MAX_CANDIDATES];

    /* Execution policies */
    uint32_t                          one_step_policy;       /* refiner_one_step_policy */
    elpis_semantic_refiner_bounded_policy_v1 bounded_policy;
    uint32_t                          failure_policy;        /* refiner_failure_policy */

    /* Timeout */
    uint32_t                          timeout_seconds;

    /* Qualification thresholds (reuse P10) */
    uint32_t                          minimum_positive_fixtures;
    uint32_t                          maximum_negative_fixtures;
    uint32_t                          maximum_wrong_final_cells;
    uint32_t                          minimum_aggregate_net_correct_gain;
    uint8_t                           require_each_stratum_improvement;
    uint8_t                           require_bounded_not_worse_than_one_step;

    /* Additional P11 requirements */
    uint8_t                           require_deterministic_replay;
    uint8_t                           require_artifact_identity;
    uint8_t                           require_p8_frame_conformance;
    uint8_t                           require_guard_conformance;
    uint8_t                           require_semantic_isolation;
    uint8_t                           require_reference_isolation;
    uint8_t                           runtime_admission;

    /* Selection order digest (computed at seal time) */
    hacf_digest                       selection_order_digest;

    /* Policy identity */
    hacf_digest                       bakeoff_policy_digest;

    uint8_t                           reserved[64];
} elpis_semantic_refiner_bakeoff_policy_v1;

/* Initialize */
void elpis_refiner_bakeoff_policy_init(
    elpis_semantic_refiner_bakeoff_policy_v1 *policy);

/* Compute identity */
int elpis_refiner_bakeoff_policy_identity(
    const elpis_semantic_refiner_bakeoff_policy_v1 *policy, hacf_digest *out);

/* Validate */
int elpis_refiner_bakeoff_policy_validate(
    const elpis_semantic_refiner_bakeoff_policy_v1 *policy);

/* Persistence */
int elpis_write_refiner_bakeoff_policy(const char *path,
    const elpis_semantic_refiner_bakeoff_policy_v1 *policy);
int elpis_read_refiner_bakeoff_policy(const char *path,
    elpis_semantic_refiner_bakeoff_policy_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
