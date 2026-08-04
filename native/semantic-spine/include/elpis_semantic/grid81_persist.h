/* elpis_semantic/grid81_persist.h — P7 persistence and serialization helpers.
 *
 * Shared utility functions for P7: digest computation, tensor construction,
 * mask building, and raw I/O helpers.
 */
#ifndef ELPIS_SEMANTIC_GRID81_PERSIST_H
#define ELPIS_SEMANTIC_GRID81_PERSIST_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Compute digest from raw bytes with a domain tag. */
int elpis_grid81_digest_bytes(
    const char *domain, const uint8_t *data, size_t len, hacf_digest *out);

/* Digest helpers for canonical tensors and masks. */
int elpis_grid81_digit_array_digest(
    const uint32_t digits[GRID81_CELL_COUNT], hacf_digest *out);
int elpis_grid81_digit_class_tensor_digest(
    const uint32_t classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT], hacf_digest *out);
int elpis_grid81_occupied_mask_digest(
    const uint32_t mask[GRID81_CELL_COUNT], hacf_digest *out);
int elpis_grid81_writable_mask_digest(
    const uint32_t mask[GRID81_CELL_COUNT], hacf_digest *out);

/* Sudoku template */
uint32_t elpis_grid81_sudoku_template_digit(uint32_t row, uint32_t col);
int elpis_grid81_sudoku_template_get(uint32_t row, uint32_t col, uint32_t *out);
int elpis_grid81_sudoku_template_validate(void);
int elpis_grid81_sudoku_template_digest(hacf_digest *out);
int elpis_grid81_validate_partial_board(const uint32_t digits[GRID81_CELL_COUNT]);
int elpis_grid81_validate_sudoku_constraints(const uint32_t digits[GRID81_CELL_COUNT]);

/* Placement */
int elpis_grid81_compute_placement(
    const elpis_semantic_grid81_codebook_v1 *codebook,
    const elpis_semantic_grid81_capsule_v1 *capsule,
    uint32_t *out_row, uint32_t *out_col, uint32_t *out_cell);
uint32_t elpis_grid81_compute_digit(uint32_t capsule_count, uint32_t row, uint32_t col);
int elpis_grid81_capsule_order_cmp(
    const elpis_semantic_grid81_capsule_v1 *a,
    const elpis_semantic_grid81_capsule_v1 *b);

/* Tensor/mask construction */
void elpis_grid81_build_digit_class_tensor(
    const uint32_t digits[GRID81_CELL_COUNT],
    uint32_t classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT]);
void elpis_grid81_build_occupied_mask(
    const uint32_t digits[GRID81_CELL_COUNT],
    uint32_t mask[GRID81_CELL_COUNT]);
void elpis_grid81_build_writable_mask(uint32_t mask[GRID81_CELL_COUNT]);

/* Digest utilities */
void elpis_grid81_zero_digest(hacf_digest *d);
int elpis_grid81_digest_is_zero(const hacf_digest *d);

#ifdef __cplusplus
}
#endif
#endif
