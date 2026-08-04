/* grid81_sudoku_template.c — Canonical Sudoku template. */
#include "elpis_semantic/grid81_policy.h"
#include "elpis/cascade.h"
#include "elpis/sha256.h"
#include <string.h>
#include <stdint.h>

/* Canonical solved Sudoku: digit(row,col) = 1 + ((row*3 + row/3 + col) % 9) */
static const uint32_t CANONICAL_TEMPLATE[9][9] = {
    {1,2,3,4,5,6,7,8,9},
    {4,5,6,7,8,9,1,2,3},
    {7,8,9,1,2,3,4,5,6},
    {2,3,4,5,6,7,8,9,1},
    {5,6,7,8,9,1,2,3,4},
    {8,9,1,2,3,4,5,6,7},
    {3,4,5,6,7,8,9,1,2},
    {6,7,8,9,1,2,3,4,5},
    {9,1,2,3,4,5,6,7,8},
};

/* Compute canonical template digit for a given row,col. */
uint32_t elpis_grid81_sudoku_template_digit(uint32_t row, uint32_t col) {
    return 1u + ((row * 3u + row / 3u + col) % 9u);
}

/* Get digit from canonical template at (row, col). Returns SEMANTIC_E_INVAL if out of range. */
int elpis_grid81_sudoku_template_get(uint32_t row, uint32_t col, uint32_t *out) {
    if (row >= 9u || col >= 9u || !out) return SEMANTIC_E_INVAL;
    *out = CANONICAL_TEMPLATE[row][col];
    return SEMANTIC_OK;
}

/* Validate the formula produces the canonical board. */
int elpis_grid81_sudoku_template_validate(void) {
    for (uint32_t r = 0; r < 9; r++) {
        for (uint32_t c = 0; c < 9; c++) {
            uint32_t d = elpis_grid81_sudoku_template_digit(r, c);
            if (d != CANONICAL_TEMPLATE[r][c]) return SEMANTIC_E_INVAL;
        }
    }
    return SEMANTIC_OK;
}

/* Compute template digest. Domain: "elpis.semantic.grid81.sudoku_template.v1" */
int elpis_grid81_sudoku_template_digest(hacf_digest *out) {
    if (!out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.grid81.sudoku_template.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    elpis_sha256_update(&ctx, (const uint8_t *)domain, 4);
    for (uint32_t r = 0; r < 9; r++) {
        for (uint32_t c = 0; c < 9; c++) {
            uint32_t d = CANONICAL_TEMPLATE[r][c];
            elpis_sha256_update(&ctx, (uint8_t *)&d, 4);
        }
    }
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

/* Validate partial board: every nonzero digit matches canonical template. */
int elpis_grid81_validate_partial_board(const uint32_t digits[GRID81_CELL_COUNT]) {
    if (!digits) return SEMANTIC_E_INVAL;
    for (uint32_t cell = 0; cell < GRID81_CELL_COUNT; cell++) {
        uint32_t row = cell / 9u;
        uint32_t col = cell % 9u;
        if (digits[cell] == 0) continue;
        if (digits[cell] > 9u) return SEMANTIC_E_INVAL;
        uint32_t canonical = elpis_grid81_sudoku_template_digit(row, col);
        if (digits[cell] != canonical) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

/* Validate partial board Sudoku constraints (rows, cols, boxes have no duplicates among nonzero). */
int elpis_grid81_validate_sudoku_constraints(const uint32_t digits[GRID81_CELL_COUNT]) {
    if (!digits) return SEMANTIC_E_INVAL;

    /* Check rows */
    for (uint32_t r = 0; r < 9; r++) {
        uint8_t seen[10] = {0};
        for (uint32_t c = 0; c < 9; c++) {
            uint32_t d = digits[r * 9u + c];
            if (d > 0 && d <= 9) {
                if (seen[d]) return SEMANTIC_E_INVAL;
                seen[d] = 1;
            }
        }
    }

    /* Check columns */
    for (uint32_t c = 0; c < 9; c++) {
        uint8_t seen[10] = {0};
        for (uint32_t r = 0; r < 9; r++) {
            uint32_t d = digits[r * 9u + c];
            if (d > 0 && d <= 9) {
                if (seen[d]) return SEMANTIC_E_INVAL;
                seen[d] = 1;
            }
        }
    }

    /* Check 3x3 boxes */
    for (uint32_t box_r = 0; box_r < 3; box_r++) {
        for (uint32_t box_c = 0; box_c < 3; box_c++) {
            uint8_t seen[10] = {0};
            for (uint32_t r = 0; r < 3; r++) {
                for (uint32_t c = 0; c < 3; c++) {
                    uint32_t row = box_r * 3u + r;
                    uint32_t col = box_c * 3u + c;
                    uint32_t d = digits[row * 9u + col];
                    if (d > 0 && d <= 9) {
                        if (seen[d]) return SEMANTIC_E_INVAL;
                        seen[d] = 1;
                    }
                }
            }
        }
    }
    return SEMANTIC_OK;
}
