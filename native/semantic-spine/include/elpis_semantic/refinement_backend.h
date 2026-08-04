/* elpis_semantic/refinement_backend.h — Canonical refinement backend ABI v1.
 *
 * Defines the backend identity, input contract, output contract, and status
 * for a structural-refinement backend registered in the P12 registry.
 *
 * Identity domain: "elpis.semantic.refinement_backend.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINEMENT_BACKEND_H
#define ELPIS_SEMANTIC_REFINEMENT_BACKEND_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/refiner_candidate.h"
#include "elpis_semantic/refiner_adapter.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINEMENT_BACKEND_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Backend status                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum refinement_backend_status {
    REFINEMENT_STATUS_ACTIVE_CANONICAL     = 0u,
    REFINEMENT_STATUS_AVAILABLE_NONCANONICAL = 1u,
    REFINEMENT_STATUS_RETIRED_NEGATIVE_CONTROL = 2u,
    REFINEMENT_STATUS_DISABLED             = 3u,
} refinement_backend_status;

/* ──────────────────────────────────────────────────────────────────── */
/* Backend identity                                                       */
/* ──────────────────────────────────────────────────────────────────── */

#define REFINEMENT_BACKEND_NAME_MAX 64u

typedef struct elpis_semantic_refinement_backend_v1 {
    uint32_t                              abi_version;

    /* Identity */
    char                                  backend_name[REFINEMENT_BACKEND_NAME_MAX];

    /* Bound candidate */
    elpis_semantic_refiner_candidate_v1   candidate_manifest;

    /* Bound adapter */
    char                                  adapter_name[REFINER_ADAPTER_NAME_MAX];

    /* Backend class (mirrors candidate class) */
    uint32_t                              candidate_class;  /* refiner_candidate_class */

    /* Capability flags */
    uint8_t                               CPU_execution_supported;
    uint8_t                               deterministic_execution_supported;
    uint8_t                               semantic_sidecar_access;  /* must be 0 */
    uint8_t                               reference_solution_access; /* must be 0 */
    uint8_t                               training_required;      /* must be 0 */

    /* Status */
    uint32_t                              status;  /* refinement_backend_status */

    /* Backend identity digest */
    hacf_digest                           backend_digest;

    uint8_t                               reserved[64];
} elpis_semantic_refinement_backend_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_refinement_backend_init(
    elpis_semantic_refinement_backend_v1 *backend);

/* Compute backend identity. Domain: "elpis.semantic.refinement_backend.v1" */
int elpis_refinement_backend_identity(
    const elpis_semantic_refinement_backend_v1 *backend, hacf_digest *out);

/* Validate: ABI version, status valid, sidecar/ref/training all zero, reserved zeroed. */
int elpis_refinement_backend_validate(
    const elpis_semantic_refinement_backend_v1 *backend);

/* Persistence */
int elpis_write_refinement_backend(const char *path,
    const elpis_semantic_refinement_backend_v1 *backend);
int elpis_read_refinement_backend(const char *path,
    elpis_semantic_refinement_backend_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
