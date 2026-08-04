/* elpis_semantic/context_iteration_policy.h — Context-iteration policy for P5.
 *
 * Defines the sealed rules governing retrieval-and-admission iteration:
 * round limits, stagnation detection, and stop behaviors.
 *
 * Identity domain: "elpis.semantic.context_iteration_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_CONTEXT_ITERATION_POLICY_H
#define ELPIS_SEMANTIC_CONTEXT_ITERATION_POLICY_H

#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CONTEXT_ITERATION_POLICY_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Policy flags                                                          */
/* ──────────────────────────────────────────────────────────────────── */

#define CONTEXT_ITERATION_FLAG_NONE              0u
#define CONTEXT_ITERATION_FAIL_CLOSED_BLOCKED    0x01u
#define CONTEXT_ITERATION_FAIL_CLOSED_INVALID    0x02u
#define CONTEXT_ITERATION_STOP_NO_PROGRESS       0x04u
#define CONTEXT_ITERATION_ROUND_LIMIT_NO_VIEW    0x08u
#define CONTEXT_ITERATION_FLAG_MASK              0xFFu

/* ──────────────────────────────────────────────────────────────────── */
/* Identical behavior for stagnation detection                           */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum context_identical_behavior {
    IDENTICAL_STOP_NO_PROGRESS  = 0,
    IDENTICAL_CONTINUE_ONE_MORE = 1
} context_identical_behavior;

/* ──────────────────────────────────────────────────────────────────── */
/* Progress measurement policy                                           */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum context_progress_measurement_policy {
    PROGRESS_MEASURE_SEMANTIC   = 0,  /* semantic delta, not byte count */
    PROGRESS_MEASURE_BLOCKED    = 1
} context_progress_measurement_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* Context iteration policy                                              */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_context_iteration_policy_v1 {
    uint32_t                abi_version;

    uint32_t                maximum_retrieval_rounds;
    uint32_t                maximum_stagnant_rounds;

    uint32_t                identical_requirement_bundle_behavior;  /* context_identical_behavior */
    uint32_t                identical_typed_view_behavior;         /* context_identical_behavior */
    uint32_t                identical_deficit_set_behavior;        /* context_identical_behavior */
    uint32_t                no_new_semantic_object_behavior;       /* context_identical_behavior */
    uint32_t                no_new_contributing_assertion_behavior; /* context_identical_behavior */

    uint32_t                blocked_evaluation_behavior;   /* context_identical_behavior */
    uint32_t                invalid_requirement_set_behavior; /* context_identical_behavior */
    uint32_t                round_limit_behavior;          /* context_identical_behavior */

    uint32_t                progress_measurement_policy;   /* context_progress_measurement_policy */

    /* Policy identity */
    hacf_digest             continuation_policy_digest;
    hacf_digest             policy_identity;
    uint32_t                policy_flags;

    uint8_t                 reserved[64];
} elpis_semantic_context_iteration_policy_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Default P5 v1 policy construction                                     */
/* ──────────────────────────────────────────────────────────────────── */

/* Construct the default P5 v1 iteration policy:
 *   maximum_retrieval_rounds: 3
 *   maximum_stagnant_rounds: 1
 *   all identical behaviors: STOP_NO_PROGRESS
 *   blocked_evaluation: FAIL_CLOSED (STOP_NO_PROGRESS)
 *   invalid_requirement_set: FAIL_CLOSED (STOP_NO_PROGRESS)
 *   round_limit: STOP_NO_PROGRESS
 *   progress_measurement: SEMANTIC
 *   policy_flags: all safety bits set
 * Returns SEMANTIC_OK on success. */
int elpis_context_iteration_policy_default(
    elpis_semantic_context_iteration_policy_v1 *policy);

/* Zero-initialize. Sets abi_version. */
void elpis_context_iteration_policy_init(
    elpis_semantic_context_iteration_policy_v1 *policy);

/* Compute policy identity. Domain: "elpis.semantic.context_iteration_policy.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *   || maximum_retrieval_rounds(4 BE)
 *   || maximum_stagnant_rounds(4 BE)
 *   || identical_requirement_bundle_behavior(4 BE)
 *   || identical_typed_view_behavior(4 BE)
 *   || identical_deficit_set_behavior(4 BE)
 *   || no_new_semantic_object_behavior(4 BE)
 *   || no_new_contributing_assertion_behavior(4 BE)
 *   || blocked_evaluation_behavior(4 BE)
 *   || invalid_requirement_set_behavior(4 BE)
 *   || round_limit_behavior(4 BE)
 *   || progress_measurement_policy(4 BE)
 *   || policy_flags(4 BE). */
int elpis_context_iteration_policy_identity(
    const elpis_semantic_context_iteration_policy_v1 *policy, hacf_digest *out);

/* Validate: known ABI, valid enums, zero reserved, positive limits,
 * valid flag mask. */
int elpis_context_iteration_policy_validate(
    const elpis_semantic_context_iteration_policy_v1 *policy);

/* Compare two policies by identity digest. Returns negative, zero, positive. */
int elpis_context_iteration_policy_cmp(
    const elpis_semantic_context_iteration_policy_v1 *a,
    const elpis_semantic_context_iteration_policy_v1 *b);

/* Persistence */
int elpis_write_iteration_policy(const char *path,
                                  const elpis_semantic_context_iteration_policy_v1 *policy);
int elpis_read_iteration_policy(const char *path,
                                 elpis_semantic_context_iteration_policy_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
