/* trm_input_validate.c — P7 input validation for TRM adapter. */

#include "elpis_semantic/grid81_handoff.h"
#include "elpis_semantic/grid81_structural_packet.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

/* Validate cell consistency: occupied==1 iff digit!=0 */
int elpis_trm_validate_P7_cell_consistency(
    const uint32_t digits[GRID81_CELL_COUNT],
    const uint32_t occupied[GRID81_CELL_COUNT])
{
    if (!digits || !occupied) return SEMANTIC_E_INVAL;

    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        int has_digit = (digits[i] != 0);
        int is_occupied = (occupied[i] == 1);

        if (has_digit != is_occupied) {
            return SEMANTIC_E_INVAL;
        }
    }
    return SEMANTIC_OK;
}

/* Validate digit-class tensor: exactly 810 binary values,
 * one active class per cell, argmax equals digit array. */
static int validate_digit_class_tensor(
    const uint32_t digit_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT],
    const uint32_t digits[GRID81_CELL_COUNT])
{
    if (!digit_classes || !digits) return SEMANTIC_E_INVAL;

    for (uint32_t cell = 0; cell < GRID81_CELL_COUNT; cell++) {
        uint32_t active_count = 0;
        uint32_t active_class = 0;

        for (uint32_t cls = 0; cls < GRID81_DIGIT_CLASS_COUNT; cls++) {
            if (digit_classes[cell][cls] != 0 && digit_classes[cell][cls] != 1) {
                return SEMANTIC_E_INVAL;
            }
            if (digit_classes[cell][cls] == 1) {
                active_count++;
                active_class = cls;
            }
        }

        if (active_count != 1) return SEMANTIC_E_INVAL;
        if (active_class != digits[cell]) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

/* Validate occupied mask: binary, length 81. */
static int validate_occupied_mask(const uint32_t occupied[GRID81_CELL_COUNT]) {
    if (!occupied) return SEMANTIC_E_INVAL;
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        if (occupied[i] != 0 && occupied[i] != 1) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

/* Validate compiler writable mask: binary, length 81, all zero. */
static int validate_compiler_writable_mask(const uint32_t writable[GRID81_CELL_COUNT]) {
    if (!writable) return SEMANTIC_E_INVAL;
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        if (writable[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

/* Validate partial Sudoku: no duplicate nonzero digits in rows, cols, boxes. */
static int validate_partial_sudoku(const uint32_t digits[GRID81_CELL_COUNT]) {
    if (!digits) return SEMANTIC_E_INVAL;

    /* Check each digit is 0-9 */
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        if (digits[i] > 9) return SEMANTIC_E_INVAL;
    }

    /* Check rows */
    for (uint32_t row = 0; row < 9; row++) {
        uint8_t seen[10] = {0};
        for (uint32_t col = 0; col < 9; col++) {
            uint32_t idx = row * 9 + col;
            uint32_t d = digits[idx];
            if (d != 0) {
                if (seen[d]) return SEMANTIC_E_INVAL;
                seen[d] = 1;
            }
        }
    }

    /* Check columns */
    for (uint32_t col = 0; col < 9; col++) {
        uint8_t seen[10] = {0};
        for (uint32_t row = 0; row < 9; row++) {
            uint32_t idx = row * 9 + col;
            uint32_t d = digits[idx];
            if (d != 0) {
                if (seen[d]) return SEMANTIC_E_INVAL;
                seen[d] = 1;
            }
        }
    }

    /* Check 3x3 boxes */
    for (uint32_t box_row = 0; box_row < 3; box_row++) {
        for (uint32_t box_col = 0; box_col < 3; box_col++) {
            uint8_t seen[10] = {0};
            for (uint32_t r = 0; r < 3; r++) {
                for (uint32_t c = 0; c < 3; c++) {
                    uint32_t idx = (box_row * 3 + r) * 9 + (box_col * 3 + c);
                    uint32_t d = digits[idx];
                    if (d != 0) {
                        if (seen[d]) return SEMANTIC_E_INVAL;
                        seen[d] = 1;
                    }
                }
            }
        }
    }
    return SEMANTIC_OK;
}

/* Validate handoff kind and boundary. */
int elpis_trm_validate_P7_input(
    const elpis_semantic_grid81_handoff_v1 *handoff,
    const elpis_semantic_grid81_structural_packet_v1 *packet)
{
    if (!handoff || !packet) return SEMANTIC_E_INVAL;

    /* Handoff kind must be GRID81_TO_TRM_ADAPTER_INPUT */
    if (handoff->handoff_kind != GRID81_TO_TRM_ADAPTER_INPUT) return SEMANTIC_E_INVAL;

    /* Validate digit array */
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        if (packet->grid81_digits[i] > 9) return SEMANTIC_E_INVAL;
    }

    /* Validate occupied mask */
    if (validate_occupied_mask(packet->occupied_mask81) < 0) return SEMANTIC_E_INVAL;

    /* Validate compiler writable mask all zero */
    if (validate_compiler_writable_mask(packet->compiler_writable_mask81) < 0) return SEMANTIC_E_INVAL;

    /* Validate digit-class tensor */
    if (validate_digit_class_tensor(packet->grid81_digit_classes,
        packet->grid81_digits) < 0) return SEMANTIC_E_INVAL;

    /* Validate cell consistency */
    if (elpis_trm_validate_P7_cell_consistency(packet->grid81_digits,
        packet->occupied_mask81) < 0) return SEMANTIC_E_INVAL;

    /* Validate partial Sudoku */
    if (validate_partial_sudoku(packet->grid81_digits) < 0) return SEMANTIC_E_INVAL;

    return SEMANTIC_OK;
}
