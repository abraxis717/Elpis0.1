/* sudoku_reference_solution.h — Deterministic evaluation-only Sudoku solver.
 *
 * Backtracking solver with MRV heuristic and ascending digit order.
 * Used ONLY for: corpus uniqueness verification, reference recovery, scoring.
 * NOT used for: TRM features, guard admission, or refinement influence.
 */
#ifndef SUDOKU_REFERENCE_SOLUTION_H
#define SUDOKU_REFERENCE_SOLUTION_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SUDOKU_CELL_COUNT 81u
#define SUDOKU_DIGIT_COUNT 9u

typedef enum sudoku_solver_result {
    SUDOKU_NO_SOLUTION = 0u,
    SUDOKU_EXACTLY_ONE_SOLUTION = 1u,
    SUDOKU_MULTIPLE_SOLUTIONS = 2u,
} sudoku_solver_result;

/* Solve with MRV cell selection, ascending digit order.
 * Returns solver result. If EXACTLY_ONE_SOLUTION, writes to output_digits.
 * max_solutions: stop search after this many (2 is sufficient for uniqueness). */
sudoku_solver_result sudoku_reference_solve(
    const uint32_t input_digits[SUDOKU_CELL_COUNT],
    const uint32_t fixed_mask[SUDOKU_CELL_COUNT],
    uint32_t output_digits[SUDOKU_CELL_COUNT],
    uint32_t max_solutions);

/* Validate a complete board: row, column, box rules. */
int sudoku_validate_complete(
    const uint32_t digits[SUDOKU_CELL_COUNT]);

/* Validate a partial board: no conflicts among filled cells. */
int sudoku_validate_partial(
    const uint32_t digits[SUDOKU_CELL_COUNT]);

#ifdef __cplusplus
}
#endif
#endif
