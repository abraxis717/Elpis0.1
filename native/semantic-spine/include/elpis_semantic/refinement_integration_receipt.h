/* elpis_semantic/refinement_integration_receipt.h — Integration receipt v1.
 *
 * Immutable receipt proving that a canonical refinement integration
 * transaction completed with bounded execution, Sudoku-valid states,
 * and all guard conformance.
 *
 * Identity domain: "elpis.semantic.refinement_integration_receipt.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINEMENT_INTEGRATION_RECEIPT_H
#define ELPIS_SEMANTIC_REFINEMENT_INTEGRATION_RECEIPT_H

#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINEMENT_INTEGRATION_RECEIPT_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Integration receipt                                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_refinement_integration_receipt_v1 {
    uint32_t                              abi_version;

    /* Request binding */
    hacf_digest                           request_digest;

    /* Policy binding */
    hacf_digest                           policy_digest;

    /* Backend binding */
    hacf_digest                           backend_digest;

    /* Adapter binding */
    hacf_digest                           adapter_digest;

    /* Execution proof */
    hacf_digest                           result_digest;

    /* Bounded execution */
    uint32_t                              steps_executed;
    uint32_t                              steps_bound;
    uint8_t                               execution_bounded;

    /* Guard conformance */
    uint8_t                               all_states_sudoku_valid;
    uint8_t                               fixed_clues_unchanged;
    uint8_t                               all_changes_writable_mask;
    uint8_t                               no_direct_state_mutation;

    /* Isolation */
    uint8_t                               semantic_sidecar_inaccessible;
    uint8_t                               reference_solution_inaccessible;

    /* Determinism */
    uint8_t                               deterministic_execution;

    /* Receipt identity */
    hacf_digest                           receipt_digest;

    uint8_t                               reserved[64];
} elpis_semantic_refinement_integration_receipt_v1;

/* Initialize */
void elpis_refinement_integration_receipt_init(
    elpis_semantic_refinement_integration_receipt_v1 *receipt);

/* Compute receipt identity */
int elpis_refinement_integration_receipt_identity(
    const elpis_semantic_refinement_integration_receipt_v1 *receipt, hacf_digest *out);

/* Validate */
int elpis_refinement_integration_receipt_validate(
    const elpis_semantic_refinement_integration_receipt_v1 *receipt);

/* Persistence */
int elpis_write_refinement_integration_receipt(const char *path,
    const elpis_semantic_refinement_integration_receipt_v1 *receipt);
int elpis_read_refinement_integration_receipt(const char *path,
    elpis_semantic_refinement_integration_receipt_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
