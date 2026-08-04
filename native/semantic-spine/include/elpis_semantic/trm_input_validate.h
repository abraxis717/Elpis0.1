/* elpis_semantic/trm_input_validate.h — P7 input validation for TRM adapter v1.
 *
 * Validates the exact P7 handoff and structural packet before TRM
 * adapter consumption.
 */
#ifndef ELPIS_SEMANTIC_TRM_INPUT_VALIDATE_H
#define ELPIS_SEMANTIC_TRM_INPUT_VALIDATE_H

#include "elpis_semantic/grid81_policy.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Forward declarations for P7 packet structures */
struct elpis_semantic_grid81_handoff_v1;
struct elpis_semantic_grid81_structural_packet_v1;

/* Validate cell consistency: occupied==1 iff digit!=0. */
int elpis_trm_validate_P7_cell_consistency(
    const uint32_t digits[GRID81_CELL_COUNT],
    const uint32_t occupied[GRID81_CELL_COUNT]);

/* Full P7 input validation: handoff kind, cell count, digit classes,
 * digit array, occupied mask, compiler_writable_mask all zero,
 * partial Sudoku validity. */
int elpis_trm_validate_P7_input(
    const struct elpis_semantic_grid81_handoff_v1 *handoff,
    const struct elpis_semantic_grid81_structural_packet_v1 *packet);

#ifdef __cplusplus
}
#endif
#endif
