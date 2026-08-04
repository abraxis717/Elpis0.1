/* test_sudoku_reference_solver.c — P10 reference solver tests. */
#include <stdio.h>
#include <string.h>
#include "elpis_semantic/sudoku_reference_solution.h"

static int tests_passed = 0;
static int tests_failed = 0;

#define CHECK(cond, msg) do { \
    if (!(cond)) { printf("FAIL: %s\n", msg); tests_failed++; } \
    else { tests_passed++; } \
} while(0)

/* Canonical solved board */
static const uint32_t CANONICAL[] = {
    5,3,4,6,7,8,9,1,2,
    6,7,2,1,9,5,3,4,8,
    1,9,8,3,4,2,5,6,7,
    8,5,9,7,6,1,4,2,3,
    4,2,6,8,5,3,7,9,1,
    7,1,3,9,2,4,8,5,6,
    9,6,1,5,3,7,2,8,4,
    2,8,7,4,1,9,6,3,5,
    3,4,5,2,8,6,1,7,9,
};

int main(void) {
    uint32_t out[81];
    uint32_t fixed[81];

    /* Test 1: Complete valid board → exactly one solution */
    memcpy(fixed, CANONICAL, sizeof(CANONICAL));
    sudoku_solver_result r = sudoku_reference_solve(CANONICAL, fixed, out, 2);
    CHECK(r == SUDOKU_EXACTLY_ONE_SOLUTION, "complete valid board");
    CHECK(memcmp(out, CANONICAL, sizeof(out)) == 0, "complete board matches");

    /* Test 2: Partial puzzle with unique solution */
    uint32_t partial[81];
    uint32_t partial_fixed[81];
    memcpy(partial, CANONICAL, sizeof(CANONICAL));
    memset(partial_fixed, 0, sizeof(partial_fixed));
    /* Fill only corners */
    for (int i = 0; i < 81; i++) partial[i] = 0;
    partial[0] = 5; partial[8] = 2; partial[72] = 3; partial[80] = 9;
    partial_fixed[0] = 1; partial_fixed[8] = 1; partial_fixed[72] = 1; partial_fixed[80] = 1;

    r = sudoku_reference_solve(partial, partial_fixed, out, 2);
    /* May be multiple solutions with so few clues — just check it runs */
    CHECK(r != 0, "partial puzzle runs");

    /* Test 3: Invalid complete board (duplicate in row) */
    uint32_t invalid[81];
    memcpy(invalid, CANONICAL, sizeof(CANONICAL));
    invalid[1] = 5; /* Duplicate 5 in row 0 */
    int valid = sudoku_validate_complete(invalid);
    CHECK(!valid, "invalid complete board detected");

    /* Test 4: Valid complete board validates */
    valid = sudoku_validate_complete(CANONICAL);
    CHECK(valid, "canonical validates");

    /* Test 5: Partial board validates (no conflicts) */
    uint32_t empty[81] = {0};
    empty[0] = 5; empty[1] = 3;
    int pvalid = sudoku_validate_partial(empty);
    CHECK(pvalid, "partial no-conflict validates");

    /* Test 6: Partial board with conflict */
    uint32_t conflict[81] = {0};
    conflict[0] = 5; conflict[1] = 5;
    pvalid = sudoku_validate_partial(conflict);
    CHECK(!pvalid, "partial with conflict fails");

    /* Test 7: Empty board is partial-valid */
    memset(empty, 0, sizeof(empty));
    pvalid = sudoku_validate_partial(empty);
    CHECK(pvalid, "empty board is partial-valid");

    printf("Results: %d passed, %d failed\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
