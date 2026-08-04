/* trm_refinement_state.h — P9 recursive structural state v1.
 *
 * Identity domain: "elpis.semantic.trm_refinement_state.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_REFINEMENT_STATE_H
#define ELPIS_SEMANTIC_TRM_REFINEMENT_STATE_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_REFINEMENT_STATE_VERSION 1u

/* Digit-class element count: [81][10] float32 */
#define TRM_REFINEMENT_STATE_CLASS_ELEMENTS (GRID81_CELL_COUNT * GRID81_DIGIT_CLASS_COUNT)

typedef struct elpis_semantic_trm_refinement_state_v1 {
    uint32_t                          abi_version;

    /* Identity bindings */
    hacf_digest                       root_P7_structural_packet_digest;
    hacf_digest                       root_P8_adapter_packet_digest;
    hacf_digest                       parent_state_digest_or_zero;
    hacf_digest                       producing_step_digest_or_zero;

    /* State index */
    uint32_t                          state_index;

    /* Grid81 digits */
    uint32_t                          grid81_digits[GRID81_CELL_COUNT];

    /* Grid81 digit-class one-hot tensor: [81][10] float32 */
    float                             grid81_digit_classes[TRM_REFINEMENT_STATE_CLASS_ELEMENTS];

    /* Static masks (digests) */
    hacf_digest                       static_fixed_mask_digest;
    hacf_digest                       static_writable_mask_digest;

    /* Content digests */
    hacf_digest                       digit_array_digest;
    hacf_digest                       digit_class_tensor_digest;
    hacf_digest                       Sudoku_validation_receipt_digest;

    /* Cell counts */
    uint32_t                          filled_cell_count;
    uint32_t                          empty_cell_count;

    /* HACF */
    hacf_digest                       HACF_package_digest;

    /* State identity */
    hacf_digest                       refinement_state_digest;

    /* Reserved */
    uint8_t                           reserved[64];
} elpis_semantic_trm_refinement_state_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_trm_refinement_state_init(
    elpis_semantic_trm_refinement_state_v1 *state);

/* Compute state identity. Domain: "elpis.semantic.trm_refinement_state.v1" */
int elpis_trm_refinement_state_identity(
    const elpis_semantic_trm_refinement_state_v1 *state, hacf_digest *out);

/* Validate: 81 digits, digits/one-hot agree, fixed cells match original,
 * changes confined to writable mask, board is Sudoku-valid, reserved zeroed. */
int elpis_trm_refinement_state_validate(
    const elpis_semantic_trm_refinement_state_v1 *state,
    const uint32_t original_P7_digits[GRID81_CELL_COUNT],
    const uint32_t static_fixed_mask[GRID81_CELL_COUNT],
    const uint32_t static_writable_mask[GRID81_CELL_COUNT]);

/* Persistence */
int elpis_write_trm_refinement_state(const char *path,
    const elpis_semantic_trm_refinement_state_v1 *state);
int elpis_read_trm_refinement_state(const char *path,
    elpis_semantic_trm_refinement_state_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
