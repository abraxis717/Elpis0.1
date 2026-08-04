/* elpis_semantic/refinement_integration_request.h — Integration request v1.
 *
 * Immutable request for canonical refinement integration. Carries only numeric
 * Grid81 state and masks. No semantic sidecar, no reference solution.
 *
 * Identity domain: "elpis.semantic.refinement_integration_request.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINEMENT_INTEGRATION_REQUEST_H
#define ELPIS_SEMANTIC_REFINEMENT_INTEGRATION_REQUEST_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINEMENT_INTEGRATION_REQUEST_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Integration request                                                      */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_refinement_integration_request_v1 {
    uint32_t                              abi_version;

    /* P7 structural packet binding */
    hacf_digest                           P7_structural_packet_digest;

    /* P8 mutability binding */
    hacf_digest                           P8_mutability_digest;

    /* Backend bindings */
    hacf_digest                           backend_registry_digest;
    hacf_digest                           active_backend_digest;
    hacf_digest                           active_adapter_digest;

    /* Integration policy binding */
    hacf_digest                           integration_policy_digest;

    /* Numeric-only input */
    hacf_digest                           initial_digit_array_digest;
    uint32_t                              initial_grid81_digits[GRID81_CELL_COUNT];

    /* Digit-class one-hot tensor: [81][10] */
    hacf_digest                           initial_digit_class_tensor_digest;
    float                                 initial_digit_classes[GRID81_CELL_COUNT * GRID81_DIGIT_CLASS_COUNT];

    /* Masks */
    hacf_digest                           fixed_mask_digest;
    uint32_t                              fixed_mask[GRID81_CELL_COUNT];

    hacf_digest                           writable_mask_digest;
    uint32_t                              writable_mask[GRID81_CELL_COUNT];

    /* HACF package */
    hacf_digest                           HACF_package_digest;

    /* Request identity digest */
    hacf_digest                           request_digest;

    uint8_t                               reserved[64];
} elpis_semantic_refinement_integration_request_v1;

/* Initialize */
void elpis_refinement_integration_request_init(
    elpis_semantic_refinement_integration_request_v1 *request);

/* Compute request identity. Domain: "elpis.semantic.refinement_integration_request.v1" */
int elpis_refinement_integration_request_identity(
    const elpis_semantic_refinement_integration_request_v1 *request, hacf_digest *out);

/* Validate: ABI version, digests match content, masks consistent, reserved zeroed. */
int elpis_refinement_integration_request_validate(
    const elpis_semantic_refinement_integration_request_v1 *request);

/* Persistence */
int elpis_write_refinement_integration_request(const char *path,
    const elpis_semantic_refinement_integration_request_v1 *request);
int elpis_read_refinement_integration_request(const char *path,
    elpis_semantic_refinement_integration_request_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
