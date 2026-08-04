/* elpis_semantic/refinement_integration_handoff.h — Integration handoff v1.
 *
 * Immutable handoff artifact binding normalized P11 replacement result,
 * backend registry, integration policy, production execution, and corpus
 * regression into a single canonical integration artifact.
 *
 * Identity domain: "elpis.semantic.refinement_integration_handoff.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINEMENT_INTEGRATION_HANDOFF_H
#define ELPIS_SEMANTIC_REFINEMENT_INTEGRATION_HANDOFF_H

#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINEMENT_INTEGRATION_HANDOFF_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Handoff kind                                                               */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum refinement_handoff_kind {
    HANDOFF_CANONICAL_STRUCTURAL_REFINER_INTEGRATED = 0u,
} refinement_handoff_kind;

/* ──────────────────────────────────────────────────────────────────── */
/* Integration handoff                                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_refinement_integration_handoff_v1 {
    uint32_t                              abi_version;

    /* Handoff kind */
    uint32_t                              handoff_kind;

    /* Normalized P11 replacement handoff */
    hacf_digest                           P11_replacement_handoff_digest;

    /* Backend registry */
    hacf_digest                           backend_registry_digest;

    /* Selected candidate manifest */
    hacf_digest                           selected_candidate_digest;

    /* Selected adapter */
    hacf_digest                           selected_adapter_digest;

    /* Integration policy */
    hacf_digest                           integration_policy_digest;

    /* Production packet execution result */
    hacf_digest                           production_execution_digest;

    /* P10 corpus regression result */
    hacf_digest                           corpus_regression_digest;

    /* Determinism receipt */
    hacf_digest                           determinism_receipt_digest;

    /* Sanitizer receipt */
    hacf_digest                           sanitizer_receipt_digest;

    /* Nonregression receipt */
    hacf_digest                           nonregression_receipt_digest;

    /* Runtime admission boundary: 0 = false */
    uint8_t                               runtime_admission;

    /* Declarations */
    uint8_t                               no_projector_target;
    uint8_t                               no_residual81;
    uint8_t                               no_training;
    uint8_t                               no_gpu_dependency;

    /* Handoff identity digest */
    hacf_digest                           handoff_digest;

    uint8_t                               reserved[128];
} elpis_semantic_refinement_integration_handoff_v1;

/* Initialize */
void elpis_refinement_integration_handoff_init(
    elpis_semantic_refinement_integration_handoff_v1 *handoff);

/* Compute handoff identity. Domain: "elpis.semantic.refinement_integration_handoff.v1" */
int elpis_refinement_integration_handoff_identity(
    const elpis_semantic_refinement_integration_handoff_v1 *handoff, hacf_digest *out);

/* Validate */
int elpis_refinement_integration_handoff_validate(
    const elpis_semantic_refinement_integration_handoff_v1 *handoff);

/* Persistence */
int elpis_write_refinement_integration_handoff(const char *path,
    const elpis_semantic_refinement_integration_handoff_v1 *handoff);
int elpis_read_refinement_integration_handoff(const char *path,
    elpis_semantic_refinement_integration_handoff_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
