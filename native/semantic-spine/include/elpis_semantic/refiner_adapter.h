/* elpis_semantic/refiner_adapter.h — Common candidate adapter ABI v1.
 *
 * Every P11 candidate adapter must consume only numeric state (Grid81 digits,
 * fixed mask, writable mask) and emit an exact P8 candidate frame.
 *
 * Identity domain: "elpis.semantic.refiner_adapter.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINER_ADAPTER_H
#define ELPIS_SEMANTIC_REFINER_ADAPTER_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/trm_candidate_frame.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINER_ADAPTER_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Adapter input                                                          */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_refiner_adapter_input_v1 {
    uint32_t                              abi_version;
    uint32_t                              grid81_digits[GRID81_CELL_COUNT];
    uint32_t                              fixed_mask[GRID81_CELL_COUNT];
    uint32_t                              writable_mask[GRID81_CELL_COUNT];
} elpis_semantic_refiner_adapter_input_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Adapter output — delegates to qualified P8 candidate frame               */
/* ──────────────────────────────────────────────────────────────────── */

/* The adapter must populate the candidate frame and set candidate_kind. */
typedef int (*refiner_adapter_execute_fn)(
    const elpis_semantic_refiner_adapter_input_v1 *input,
    elpis_semantic_trm_candidate_frame_v1 *frame);

/* ──────────────────────────────────────────────────────────────────── */
/* Adapter registration table                                               */
/* ──────────────────────────────────────────────────────────────────── */

#define REFINER_ADAPTER_NAME_MAX 64u

typedef struct elpis_semantic_refiner_adapter_v1 {
    uint32_t                              abi_version;
    char                                  adapter_name[REFINER_ADAPTER_NAME_MAX];
    refiner_adapter_execute_fn            execute;
    int                                   conformance_pass;
    uint8_t                               reserved[64];
} elpis_semantic_refiner_adapter_v1;

void elpis_refiner_adapter_init(elpis_semantic_refiner_adapter_v1 *adapter);
int elpis_refiner_adapter_validate(const elpis_semantic_refiner_adapter_v1 *adapter);

#ifdef __cplusplus
}
#endif
#endif
