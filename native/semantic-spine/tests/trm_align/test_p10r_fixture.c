/* P10R fixture validation test */
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "elpis_semantic/trm_alignment_fixture.h"

int main(void) {
    /* Test valid complete Sudoku */
    int8_t valid_solution[TRM_FIXTURE_CELL_COUNT] = {
        1,2,3,4,5,6,7,8,9,
        4,5,6,7,8,9,1,2,3,
        7,8,9,1,2,3,4,5,6,
        2,3,4,5,6,7,8,9,1,
        5,6,7,8,9,1,2,3,4,
        8,9,1,2,3,4,5,6,7,
        3,4,5,6,7,8,9,1,2,
        6,7,8,9,1,2,3,4,5,
        9,1,2,3,4,5,6,7,8,
    };
    assert(trm_fixture_is_sudoku_valid(valid_solution));

    /* Test valid partial board (all zeros) */
    int8_t empty_board[TRM_FIXTURE_CELL_COUNT] = {0};
    assert(trm_fixture_is_sudoku_valid(empty_board));

    /* Test invalid board (duplicate in row) */
    int8_t invalid_row[TRM_FIXTURE_CELL_COUNT] = {0};
    invalid_row[0] = 1;
    invalid_row[1] = 1;  /* duplicate */
    assert(!trm_fixture_is_sudoku_valid(invalid_row));

    /* Test invalid board (duplicate in column) */
    int8_t invalid_col[TRM_FIXTURE_CELL_COUNT] = {0};
    invalid_col[0] = 5;
    invalid_col[9] = 5;  /* duplicate column */
    assert(!trm_fixture_is_sudoku_valid(invalid_col));

    /* Test invalid board (duplicate in box) */
    int8_t invalid_box[TRM_FIXTURE_CELL_COUNT] = {0};
    invalid_box[0] = 3;
    invalid_box[2] = 3;  /* duplicate in same box */
    assert(!trm_fixture_is_sudoku_valid(invalid_box));

    /* Test fixture count metrics */
    assert(trm_fixture_count_correct(valid_solution, valid_solution) == 81);

    int8_t half_board[TRM_FIXTURE_CELL_COUNT] = {0};
    for (int i = 0; i < 81; i++) half_board[i] = valid_solution[i];
    assert(trm_fixture_count_correct(half_board, valid_solution) == 81);

    /* Test fixture set creation and sealing */
    trm_fixture_set_t set = trm_fixture_set_create(TRM_FIXTURE_SET_B);
    assert(set.fixture_count == 0);
    assert(!trm_fixture_set_is_sealed(&set));

    trm_fixture_t fixture;
    memset(&fixture, 0, sizeof(fixture));
    fixture.ordinal = 0;
    fixture.clue_count = 70;
    memcpy(fixture.digits, valid_solution, sizeof(valid_solution));
    for (int i = 0; i < 81; i++) {
        fixture.fixed_mask[i] = (i < 70) ? 1 : 0;
        fixture.solution[i] = valid_solution[i];
    }
    trm_fixture_compute_digest(&fixture);
    assert(fixture.fixture_digest[0] != '\0');

    assert(trm_fixture_add(&set, fixture));
    assert(set.fixture_count == 1);

    assert(trm_fixture_set_seal(&set));
    assert(trm_fixture_set_is_sealed(&set));

    /* Sealed set cannot accept more fixtures */
    memset(&fixture, 0, sizeof(fixture));
    fixture.ordinal = 1;
    assert(!trm_fixture_add(&set, fixture));

    /* Digest is non-empty after seal */
    assert(set.set_digest[0] != '\0');

    /* Null safety */
    assert(!trm_fixture_add(NULL, fixture));
    assert(!trm_fixture_set_seal(NULL));
    assert(!trm_fixture_set_is_sealed(NULL));

    printf("PASS: test_fixture_validation\n");
    return 0;
}
