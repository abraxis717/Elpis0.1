#include "elpis_semantic/trm_alignment_fixture.h"
#include <string.h>
#include <stdlib.h>

/* Deterministic fixture generation for diagnostic sets.
 * Python generates actual fixtures; C validates them. */

int trm_fixture_validate_sudoku(const trm_fixture_t *fixture) {
    return trm_fixture_is_sudoku_valid(fixture->digits);
}

int trm_fixture_validate_solution(const trm_fixture_t *fixture) {
    /* Solution must be a complete valid Sudoku (no zeros) */
    for (int i = 0; i < TRM_FIXTURE_CELL_COUNT; i++) {
        if (fixture->solution[i] == 0) return 0;
    }
    return trm_fixture_is_sudoku_valid(fixture->solution);
}

int trm_fixture_validate_partial(const trm_fixture_t *fixture) {
    return trm_fixture_is_sudoku_valid(fixture->digits) &&
           trm_fixture_validate_solution(fixture);
}
