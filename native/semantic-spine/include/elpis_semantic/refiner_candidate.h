/* elpis_semantic/refiner_candidate.h — Refiner candidate identity v1.
 *
 * Immutable candidate manifest for P11 bakeoff.
 * Identity domain: "elpis.semantic.refiner_candidate.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINER_CANDIDATE_H
#define ELPIS_SEMANTIC_REFINER_CANDIDATE_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINER_CANDIDATE_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Candidate class                                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum refiner_candidate_class {
    REFINER_CLASS_FROZEN_NEURAL       = 0u,
    REFINER_CLASS_DET_RULE            = 1u,
    REFINER_CLASS_DET_SEARCH          = 2u,
    REFINER_CLASS_HYBRID_STRUCTURAL   = 3u,
} refiner_candidate_class;

/* ──────────────────────────────────────────────────────────────────── */
/* Eligibility disposition                                                  */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum refiner_eligibility_disposition {
    REFINER_ADMISSIBLE                     = 0u,
    REFINER_INADMISSIBLE_WRONG_ABI         = 1u,
    REFINER_INADMISSIBLE_NONDETERMINISTIC  = 2u,
    REFINER_INADMISSIBLE_GPU_ONLY          = 3u,
    REFINER_INADMISSIBLE_REQUIRES_TRAINING = 4u,
    REFINER_INADMISSIBLE_REFERENCE_LEAKAGE = 5u,
    REFINER_INADMISSIBLE_SEMANTIC_SIDECAR  = 6u,
    REFINER_INADMISSIBLE_NOT_EXECUTABLE    = 7u,
    REFINER_RETIRED_NEGATIVE_CONTROL       = 8u,
} refiner_eligibility_disposition;

/* ──────────────────────────────────────────────────────────────────── */
/* Candidate manifest                                                       */
/* ──────────────────────────────────────────────────────────────────── */

#define REFINER_MAX_SOURCE_DIGESTS    8u
#define REFINER_MAX_CONFIG_DIGESTS    4u
#define REFINER_MAX_WEIGHT_DIGESTS    4u
#define REFINER_CANDIDATE_NAME_MAX    64u

typedef struct elpis_semantic_refiner_candidate_v1 {
    uint32_t                          abi_version;

    /* Identity */
    char                              candidate_name[REFINER_CANDIDATE_NAME_MAX];

    /* Classification */
    uint32_t                          candidate_class;  /* refiner_candidate_class */

    /* Source digests (ordered SHA-256) */
    uint32_t                          source_digest_count;
    hacf_digest                       source_digests[REFINER_MAX_SOURCE_DIGESTS];

    /* Configuration digests (ordered SHA-256) */
    uint32_t                          config_digest_count;
    hacf_digest                       config_digests[REFINER_MAX_CONFIG_DIGESTS];

    /* Weight digests (ordered SHA-256, zero count if not neural) */
    uint32_t                          weight_digest_count;
    hacf_digest                       weight_digests[REFINER_MAX_WEIGHT_DIGESTS];

    /* Native contracts */
    hacf_digest                       native_input_contract_digest;
    hacf_digest                       native_output_contract_digest;

    /* Capability flags */
    uint8_t                           CPU_execution_supported;
    uint8_t                           deterministic_execution_supported;
    uint8_t                           training_required;
    uint8_t                           reference_solution_access;
    uint8_t                           semantic_sidecar_access;

    /* Parameter count (0 for non-neural) */
    uint64_t                          candidate_parameter_count;

    /* Eligibility */
    uint32_t                          eligibility_disposition;

    /* Manifest identity */
    hacf_digest                       candidate_manifest_digest;

    uint8_t                           reserved[64];
} elpis_semantic_refiner_candidate_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_refiner_candidate_init(
    elpis_semantic_refiner_candidate_v1 *candidate);

/* Compute manifest identity. Domain: "elpis.semantic.refiner_candidate.v1" */
int elpis_refiner_candidate_identity(
    const elpis_semantic_refiner_candidate_v1 *candidate, hacf_digest *out);

/* Validate: ABI version, disposition valid, admissible checks, reserved zeroed. */
int elpis_refiner_candidate_validate(
    const elpis_semantic_refiner_candidate_v1 *candidate);

/* Persistence */
int elpis_write_refiner_candidate(const char *path,
    const elpis_semantic_refiner_candidate_v1 *candidate);
int elpis_read_refiner_candidate(const char *path,
    elpis_semantic_refiner_candidate_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
