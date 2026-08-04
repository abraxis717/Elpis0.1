/* sudoku_reference_solver.c — Deterministic evaluation-only Sudoku solver.
 *
 * MRV cell selection, ascending digit order, stops after 2 solutions.
 */
#include "elpis_semantic/sudoku_reference_solution.h"
#include <string.h>

static const uint32_t BOX_STARTS[9] = {
    0, 3, 6, 27, 30, 33, 54, 57, 60
};

static int is_legal(const uint32_t board[SUDOKU_CELL_COUNT],
                    uint32_t cell, uint32_t digit) {
    if (digit < 1 || digit > 9) return 0;
    uint32_t row = cell / 9;
    uint32_t col = cell % 9;
    /* Check row */
    for (uint32_t c = 0; c < 9; c++) {
        uint32_t idx = row * 9 + c;
        if (idx != cell && board[idx] == digit) return 0;
    }
    /* Check column */
    for (uint32_t r = 0; r < 9; r++) {
        uint32_t idx = r * 9 + col;
        if (idx != cell && board[idx] == digit) return 0;
    }
    /* Check box */
    uint32_t box_row = row / 3 * 3;
    uint32_t box_col = col / 3 * 3;
    for (uint32_t r = box_row; r < box_row + 3; r++) {
        for (uint32_t c = box_col; c < box_col + 3; c++) {
            uint32_t idx = r * 9 + c;
            if (idx != cell && board[idx] == digit) return 0;
        }
    }
    return 1;
}

static uint32_t domain_size(const uint32_t board[SUDOKU_CELL_COUNT],
                            uint32_t cell) {
    uint32_t count = 0;
    for (uint32_t d = 1; d <= 9; d++) {
        if (is_legal(board, cell, d)) count++;
    }
    return count;
}

static int find_mrv_cell(const uint32_t board[SUDOKU_CELL_COUNT],
                         const uint32_t fixed_mask[SUDOKU_CELL_COUNT],
                         uint32_t *best_cell) {
    uint32_t min_domain = 10;
    *best_cell = 81;
    for (uint32_t c = 0; c < 81; c++) {
        if (fixed_mask[c] || board[c] != 0) continue;
        uint32_t ds = domain_size(board, c);
        if (ds < min_domain) {
            min_domain = ds;
            *best_cell = c;
        }
    }
    if (*best_cell >= 81) return 0; /* No empty cell found */
    if (min_domain == 0) return -1; /* Dead end */
    return 1;
}

static void backtrack(uint32_t board[SUDOKU_CELL_COUNT],
                      const uint32_t fixed_mask[SUDOKU_CELL_COUNT],
                      uint32_t *solution_count,
                      uint32_t max_solutions,
                      uint32_t result[SUDOKU_CELL_COUNT]) {
    if (*solution_count >= max_solutions) return;

    uint32_t cell;
    int status = find_mrv_cell(board, fixed_mask, &cell);
    if (status <= 0) {
        /* No more empty cells or dead end */
        if (status == 0) {
            (*solution_count)++;
            if (*solution_count == 1) {
                memcpy(result, board, sizeof(uint32_t) * SUDOKU_CELL_COUNT);
            }
        }
        return;
    }

    for (uint32_t d = 1; d <= 9; d++) {
        if (is_legal(board, cell, d)) {
            board[cell] = d;
            backtrack(board, fixed_mask, solution_count, max_solutions, result);
            if (*solution_count >= max_solutions) {
                board[cell] = 0;
                return;
            }
            board[cell] = 0;
        }
    }
}

sudoku_solver_result sudoku_reference_solve(
    const uint32_t input_digits[SUDOKU_CELL_COUNT],
    const uint32_t fixed_mask[SUDOKU_CELL_COUNT],
    uint32_t output_digits[SUDOKU_CELL_COUNT],
    uint32_t max_solutions) {
    uint32_t board[SUDOKU_CELL_COUNT];
    memcpy(board, input_digits, sizeof(uint32_t) * SUDOKU_CELL_COUNT);
    uint32_t solution_count = 0;
    memset(output_digits, 0, sizeof(uint32_t) * SUDOKU_CELL_COUNT);

    uint32_t effective_max = (max_solutions > 0 && max_solutions < 2) ? 2 : max_solutions;
    backtrack(board, fixed_mask, &solution_count, effective_max, output_digits);

    if (solution_count == 0) return SUDOKU_NO_SOLUTION;
    if (solution_count == 1) return SUDOKU_EXACTLY_ONE_SOLUTION;
    return SUDOKU_MULTIPLE_SOLUTIONS;
}

int sudoku_validate_complete(
    const uint32_t digits[SUDOKU_CELL_COUNT]) {
    /* Check every cell is filled */
    for (uint32_t i = 0; i < 81; i++) {
        if (digits[i] < 1 || digits[i] > 9) return 0;
    }
    /* Check rows */
    for (uint32_t r = 0; r < 9; r++) {
        uint8_t seen[10] = {0};
        for (uint32_t c = 0; c < 9; c++) {
            uint32_t d = digits[r * 9 + c];
            if (seen[d]) return 0;
            seen[d] = 1;
        }
    }
    /* Check columns */
    for (uint32_t c = 0; c < 9; c++) {
        uint8_t seen[10] = {0};
        for (uint32_t r = 0; r < 9; r++) {
            uint32_t d = digits[r * 9 + c];
            if (seen[d]) return 0;
            seen[d] = 1;
        }
    }
    /* Check boxes */
    for (uint32_t br = 0; br < 3; br++) {
        for (uint32_t bc = 0; bc < 3; bc++) {
            uint8_t seen[10] = {0};
            for (uint32_t r = br * 3; r < br * 3 + 3; r++) {
                for (uint32_t c = bc * 3; c < bc * 3 + 3; c++) {
                    uint32_t d = digits[r * 9 + c];
                    if (seen[d]) return 0;
                    seen[d] = 1;
                }
            }
        }
    }
    return 1;
}

int sudoku_validate_partial(
    const uint32_t digits[SUDOKU_CELL_COUNT]) {
    /* Check rows */
    for (uint32_t r = 0; r < 9; r++) {
        uint8_t seen[10] = {0};
        for (uint32_t c = 0; c < 9; c++) {
            uint32_t d = digits[r * 9 + c];
            if (d == 0) continue;
            if (d < 1 || d > 9) return 0;
            if (seen[d]) return 0;
            seen[d] = 1;
        }
    }
    /* Check columns */
    for (uint32_t c = 0; c < 9; c++) {
        uint8_t seen[10] = {0};
        for (uint32_t r = 0; r < 9; r++) {
            uint32_t d = digits[r * 9 + c];
            if (d == 0) continue;
            if (seen[d]) return 0;
            seen[d] = 1;
        }
    }
    /* Check boxes */
    for (uint32_t br = 0; br < 3; br++) {
        for (uint32_t bc = 0; bc < 3; bc++) {
            uint8_t seen[10] = {0};
            for (uint32_t r = br * 3; r < br * 3 + 3; r++) {
                for (uint32_t c = bc * 3; c < bc * 3 + 3; c++) {
                    uint32_t d = digits[r * 9 + c];
                    if (d == 0) continue;
                    if (seen[d]) return 0;
                    seen[d] = 1;
                }
            }
        }
    }
    return 1;
}
