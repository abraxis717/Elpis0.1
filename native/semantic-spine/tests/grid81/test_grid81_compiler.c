/* test_grid81_compiler.c — P7 Grid81 structural compiler tests. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <stdint.h>

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/grid81_codebook.h"
#include "elpis_semantic/grid81_capsule.h"
#include "elpis_semantic/grid81_cell.h"
#include "elpis_semantic/grid81_constraint_projection.h"
#include "elpis_semantic/grid81_structural_packet.h"
#include "elpis_semantic/grid81_compile_receipt.h"
#include "elpis_semantic/grid81_handoff.h"
#include "elpis_semantic/grid81_persist.h"
#include "elpis/cascade.h"
#include "elpis/sha256.h"

static int tests_passed = 0;
static int tests_failed = 0;

#define TEST(name) do { \
    printf("  TEST %-60s ", #name); \
    if (test_##name()) { \
        printf("PASS\n"); tests_passed++; \
    } else { \
        printf("FAIL\n"); tests_failed++; \
    } \
} while(0)

/* ========================================================================= */
/* ABI and Policy tests                                                      */
/* ========================================================================= */

static int test_policy_init_and_defaults(void) {
    elpis_semantic_grid81_policy_v1 p;
    elpis_grid81_policy_init(&p);
    if (p.abi_version != GRID81_POLICY_ABI_VERSION) return 0;
    if (p.cell_count != GRID81_CELL_COUNT) return 0;
    if (p.row_count != GRID81_ROW_COUNT) return 0;
    if (p.column_count != GRID81_COLUMN_COUNT) return 0;
    if (p.digit_class_count != GRID81_DIGIT_CLASS_COUNT) return 0;
    if (p.maximum_capsules != GRID81_DEFAULT_MAX_CAPSULES) return 0;
    if (p.maximum_capsules_per_cell != GRID81_DEFAULT_MAX_CAPSULES_PER_CELL) return 0;
    if (p.maximum_vertices_per_capsule != GRID81_DEFAULT_MAX_VERTICES_PER_CAPSULE) return 0;
    if (p.maximum_vertices_per_cell != GRID81_DEFAULT_MAX_VERTICES_PER_CELL) return 0;
    if (p.maximum_constraints_per_cell != GRID81_DEFAULT_MAX_CONSTRAINTS_PER_CELL) return 0;
    return 1;
}

static int test_policy_81_cell_contract(void) {
    elpis_semantic_grid81_policy_v1 p;
    elpis_grid81_policy_init(&p);
    return (p.cell_count == 81u && p.row_count == 9u && p.column_count == 9u);
}

static int test_policy_10_digit_classes(void) {
    elpis_semantic_grid81_policy_v1 p;
    elpis_grid81_policy_init(&p);
    return (p.digit_class_count == 10u);
}

static int test_policy_validate(void) {
    elpis_semantic_grid81_policy_v1 p;
    elpis_grid81_policy_init(&p);
    int rc = elpis_grid81_policy_validate(&p);
    return (rc == SEMANTIC_OK);
}

static int test_policy_validate_null(void) {
    int rc = elpis_grid81_policy_validate(NULL);
    return (rc == SEMANTIC_E_INVAL);
}

static int test_policy_reserved_zeroed(void) {
    elpis_semantic_grid81_policy_v1 p;
    elpis_grid81_policy_init(&p);
    for (size_t i = 0; i < sizeof(p.reserved); i++) {
        if (p.reserved[i] != 0) return 0;
    }
    return 1;
}

static int test_policy_identity_determinism(void) {
    elpis_semantic_grid81_policy_v1 p1, p2;
    elpis_grid81_policy_init(&p1);
    elpis_grid81_policy_init(&p2);
    hacf_digest d1, d2;
    elpis_grid81_policy_identity(&p1, &d1);
    elpis_grid81_policy_identity(&p2, &d2);
    return (memcmp(d1.bytes, d2.bytes, HACF_DIGEST_BYTES) == 0);
}

static int test_policy_capacity_overflow_fail_closed(void) {
    elpis_semantic_grid81_policy_v1 p;
    elpis_grid81_policy_init(&p);
    return (p.overflow_policy == GRID81_FAIL_CLOSED);
}

static int test_policy_writable_mask_fixed_zero(void) {
    elpis_semantic_grid81_policy_v1 p;
    elpis_grid81_policy_init(&p);
    return (p.writable_mask_policy == GRID81_COMPILER_FIXED_ALL_ZERO);
}

/* ========================================================================= */
/* Codebook tests                                                            */
/* ========================================================================= */

static int test_codebook_init_all_lanes(void) {
    elpis_semantic_grid81_codebook_v1 cb;
    elpis_grid81_codebook_init(&cb);
    uint32_t col;
    const uint32_t expected[] = {0,1,2,3,4,5,6,7,8,8};
    for (uint32_t i = 0; i < 10; i++) {
        if (elpis_grid81_codebook_lookup(&cb, i, &col) != SEMANTIC_OK) return 0;
        if (col != expected[i]) return 0;
    }
    return 1;
}

static int test_codebook_support_contradiction_distinct(void) {
    elpis_semantic_grid81_codebook_v1 cb;
    elpis_grid81_codebook_init(&cb);
    uint32_t sup, con;
    elpis_grid81_codebook_lookup(&cb, 2, &sup);
    elpis_grid81_codebook_lookup(&cb, 3, &con);
    return (sup != con);
}

static int test_codebook_qualifier_scope_distinct(void) {
    elpis_semantic_grid81_codebook_v1 cb;
    elpis_grid81_codebook_init(&cb);
    uint32_t qual, scope;
    elpis_grid81_codebook_lookup(&cb, 4, &qual);
    elpis_grid81_codebook_lookup(&cb, 5, &scope);
    return (qual != scope);
}

static int test_codebook_unknown_lane_fails(void) {
    elpis_semantic_grid81_codebook_v1 cb;
    elpis_grid81_codebook_init(&cb);
    uint32_t col;
    int rc = elpis_grid81_codebook_lookup(&cb, 99, &col);
    return (rc == SEMANTIC_E_INVAL);
}

static int test_codebook_identity_determinism(void) {
    elpis_semantic_grid81_codebook_v1 cb1, cb2;
    elpis_grid81_codebook_init(&cb1);
    elpis_grid81_codebook_init(&cb2);
    hacf_digest d1, d2;
    elpis_grid81_codebook_identity(&cb1, &d1);
    elpis_grid81_codebook_identity(&cb2, &d2);
    return (memcmp(d1.bytes, d2.bytes, HACF_DIGEST_BYTES) == 0);
}

static int test_codebook_validate(void) {
    elpis_semantic_grid81_codebook_v1 cb;
    elpis_grid81_codebook_init(&cb);
    return (elpis_grid81_codebook_validate(&cb) == SEMANTIC_OK);
}

static int test_codebook_nonauthority_flags(void) {
    elpis_semantic_grid81_codebook_v1 cb;
    elpis_grid81_codebook_init(&cb);
    return (cb.lane_does_not_determine_digit && cb.column_does_not_encode_semantic);
}

/* ========================================================================= */
/* Sudoku template tests                                                     */
/* ========================================================================= */

static int test_sudoku_template_formula(void) {
    /* digit(row,col) = 1 + ((row*3 + row/3 + col) % 9) */
    /* Row 0: 1 2 3 4 5 6 7 8 9 */
    for (uint32_t c = 0; c < 9; c++) {
        uint32_t d = elpis_grid81_sudoku_template_digit(0, c);
        if (d != (1u + c)) return 0;
    }
    /* Row 1: 4 5 6 7 8 9 1 2 3 */
    const uint32_t row1[] = {4,5,6,7,8,9,1,2,3};
    for (uint32_t c = 0; c < 9; c++) {
        uint32_t d = elpis_grid81_sudoku_template_digit(1, c);
        if (d != row1[c]) return 0;
    }
    return 1;
}

static int test_sudoku_template_full_board(void) {
    const uint32_t expected[9][9] = {
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
    for (uint32_t r = 0; r < 9; r++) {
        for (uint32_t c = 0; c < 9; c++) {
            uint32_t d = elpis_grid81_sudoku_template_digit(r, c);
            if (d != expected[r][c]) return 0;
        }
    }
    return 1;
}

static int test_sudoku_template_validate(void) {
    return (elpis_grid81_sudoku_template_validate() == SEMANTIC_OK);
}

static int test_sudoku_template_digest_determinism(void) {
    hacf_digest d1, d2;
    elpis_grid81_sudoku_template_digest(&d1);
    elpis_grid81_sudoku_template_digest(&d2);
    return (memcmp(d1.bytes, d2.bytes, HACF_DIGEST_BYTES) == 0);
}

static int test_sudoku_partial_board_valid(void) {
    uint32_t digits[81] = {0};
    /* Place digits at a few cells */
    digits[0] = 1;   /* (0,0) -> 1 */
    digits[45] = 8;  /* (5,0) -> 8 */
    return (elpis_grid81_validate_partial_board(digits) == SEMANTIC_OK);
}

static int test_sudoku_partial_board_invalid_digit(void) {
    uint32_t digits[81] = {0};
    digits[0] = 5;   /* (0,0) should be 1, not 5 */
    return (elpis_grid81_validate_partial_board(digits) == SEMANTIC_E_INVAL);
}

static int test_sudoku_constraints_valid(void) {
    uint32_t digits[81] = {0};
    /* Fill one row with unique nonzero digits matching template */
    for (uint32_t c = 0; c < 9; c++) {
        digits[c] = elpis_grid81_sudoku_template_digit(0, c);
    }
    return (elpis_grid81_validate_sudoku_constraints(digits) == SEMANTIC_OK);
}

static int test_sudoku_constraints_duplicate(void) {
    uint32_t digits[81] = {0};
    digits[0] = 1;
    digits[1] = 1;  /* duplicate in row 0 */
    return (elpis_grid81_validate_sudoku_constraints(digits) == SEMANTIC_E_INVAL);
}

/* ========================================================================= */
/* Capsule tests                                                             */
/* ========================================================================= */

static int test_capsule_init(void) {
    elpis_semantic_grid81_capsule_v1 c;
    elpis_grid81_capsule_init(&c);
    if (c.abi_version != GRID81_CAPSULE_ABI_VERSION) return 0;
    if (c.vertex_count != 0) return 0;
    for (size_t i = 0; i < sizeof(c.reserved); i++) {
        if (c.reserved[i] != 0) return 0;
    }
    return 1;
}

static int test_capsule_validate(void) {
    elpis_semantic_grid81_capsule_v1 c;
    elpis_grid81_capsule_init(&c);
    return (elpis_grid81_capsule_validate(&c) == SEMANTIC_OK);
}

static int test_capsule_validate_null(void) {
    return (elpis_grid81_capsule_validate(NULL) == SEMANTIC_E_INVAL);
}

static int test_capsule_key_equality(void) {
    grid81_capsule_key_v1 k1, k2;
    memset(&k1, 0, sizeof(k1));
    memset(&k2, 0, sizeof(k2));
    k1.primary_lane = 2; k2.primary_lane = 2;
    k1.primary_role = 1; k2.primary_role = 1;
    k1.semantic_stratum = 3; k2.semantic_stratum = 3;
    k1.primary_constellation_index = 0; k2.primary_constellation_index = 0;
    int rc = elpis_grid81_capsule_key_cmp(&k1, &k2);
    return (rc == 0);
}

static int test_capsule_key_inequality_different_lane(void) {
    grid81_capsule_key_v1 k1, k2;
    memset(&k1, 0, sizeof(k1));
    memset(&k2, 0, sizeof(k2));
    k1.primary_lane = 2; k2.primary_lane = 3;
    int rc = elpis_grid81_capsule_key_cmp(&k1, &k2);
    return (rc != 0);
}

static int test_capsule_key_order(void) {
    grid81_capsule_key_v1 k1, k2;
    memset(&k1, 0, sizeof(k1));
    memset(&k2, 0, sizeof(k2));
    k1.primary_lane = 2; k2.primary_lane = 3;
    int rc = elpis_grid81_capsule_key_cmp_order(&k1, &k2);
    return (rc < 0);
}
static int test_capsule_manifest_init(void) {
    /* Capsule manifest is ~20MB — allocate on heap, not stack. */
    elpis_semantic_grid81_capsule_manifest_v1 *m =
        malloc(sizeof(elpis_semantic_grid81_capsule_manifest_v1));
    if (!m) return 0;
    elpis_grid81_capsule_manifest_init(m);
    int result = (m->abi_version == GRID81_CAPSULE_ABI_VERSION && m->capsule_count == 0);
    free(m);
    return result;
}

/* ========================================================================= */
/* Placement tests                                                           */
/* ========================================================================= */

static int test_placement_column_from_lane_only(void) {
    elpis_semantic_grid81_codebook_v1 cb;
    elpis_grid81_codebook_init(&cb);
    elpis_semantic_grid81_capsule_v1 cap;
    elpis_grid81_capsule_init(&cap);
    cap.primary_lane = 3; /* CONTRADICTION -> col 3 */
    cap.primary_constellation_index = 0;
    cap.semantic_stratum = 0;
    uint32_t row, col, cell;
    int rc = elpis_grid81_compute_placement(&cb, &cap, &row, &col, &cell);
    if (rc != SEMANTIC_OK) return 0;
    return (col == 3u && row == 0u && cell == 3u);
}

static int test_placement_row_formula(void) {
    elpis_semantic_grid81_codebook_v1 cb;
    elpis_grid81_codebook_init(&cb);
    elpis_semantic_grid81_capsule_v1 cap;
    elpis_grid81_capsule_init(&cap);
    cap.primary_lane = 0; /* CORE -> col 0 */
    cap.primary_constellation_index = 7;
    cap.semantic_stratum = 5;
    uint32_t row, col, cell;
    elpis_grid81_compute_placement(&cb, &cap, &row, &col, &cell);
    /* row = (7 + 5) % 9 = 12 % 9 = 3 */
    /* cell = 3 * 9 + 0 = 27 */
    return (row == 3u && col == 0u && cell == 27u);
}

static int test_placement_cell_range(void) {
    elpis_semantic_grid81_codebook_v1 cb;
    elpis_grid81_codebook_init(&cb);
    elpis_semantic_grid81_capsule_v1 cap;
    elpis_grid81_capsule_init(&cap);
    cap.primary_lane = 8; /* METRIC -> col 8 */
    cap.primary_constellation_index = 8;
    cap.semantic_stratum = 8;
    uint32_t row, col, cell;
    int rc = elpis_grid81_compute_placement(&cb, &cap, &row, &col, &cell);
    /* row = (8+8)%9 = 16%9 = 7, col = 8, cell = 7*9+8 = 71 */
    if (rc != SEMANTIC_OK) return 0;
    return (cell < GRID81_CELL_COUNT);
}

static int test_placement_digit_empty(void) {
    uint32_t d = elpis_grid81_compute_digit(0, 0, 0);
    return (d == 0u);
}

static int test_placement_digit_occupied(void) {
    uint32_t d = elpis_grid81_compute_digit(1, 0, 0);
    return (d == 1u); /* canonical template digit at (0,0) = 1 */
}

/* ========================================================================= */
/* Cell record and mask tests                                                */
/* ========================================================================= */

static int test_cell_init(void) {
    elpis_semantic_grid81_cell_v1 c;
    elpis_grid81_cell_init(&c);
    return (c.abi_version == GRID81_CELL_ABI_VERSION);
}

static int test_cell_validate_empty(void) {
    elpis_semantic_grid81_cell_v1 c;
    elpis_grid81_cell_init(&c);
    c.cell_index = 0;
    c.row = 0;
    c.column = 0;
    c.digit = 0;
    c.occupied = 0;
    c.compiler_writable = 0;
    return (elpis_grid81_cell_validate(&c) == SEMANTIC_OK);
}

static int test_cell_validate_occupied_agrees(void) {
    elpis_semantic_grid81_cell_v1 c;
    elpis_grid81_cell_init(&c);
    c.cell_index = 0;
    c.row = 0;
    c.column = 0;
    c.digit = 1;
    c.occupied = 1;
    c.capsule_count = 1;
    c.compiler_writable = 0;
    return (elpis_grid81_cell_validate(&c) == SEMANTIC_OK);
}

static int test_cell_validate_writable_must_be_zero(void) {
    elpis_semantic_grid81_cell_v1 c;
    elpis_grid81_cell_init(&c);
    c.cell_index = 0;
    c.row = 0;
    c.column = 0;
    c.digit = 0;
    c.occupied = 0;
    c.compiler_writable = 1; /* P7 requires all zero */
    return (elpis_grid81_cell_validate(&c) == SEMANTIC_E_INVAL);
}

static int test_masks_init_all_zero(void) {
    elpis_semantic_grid81_masks_v1 m;
    elpis_grid81_masks_init(&m);
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        if (m.occupied_mask81[i] != 0) return 0;
        if (m.compiler_writable_mask81[i] != 0) return 0;
    }
    return 1;
}

static int test_masks_validate_all_zero_writable(void) {
    elpis_semantic_grid81_masks_v1 m;
    elpis_grid81_masks_init(&m);
    return (elpis_grid81_masks_validate(&m) == SEMANTIC_OK);
}

static int test_masks_validate_nonzero_writable(void) {
    elpis_semantic_grid81_masks_v1 m;
    elpis_grid81_masks_init(&m);
    m.compiler_writable_mask81[0] = 1;
    return (elpis_grid81_masks_validate(&m) == SEMANTIC_E_INVAL);
}

/* ========================================================================= */
/* Digit-class tensor tests                                                  */
/* ========================================================================= */

static int test_digit_class_build(void) {
    uint32_t digits[81] = {0};
    digits[0] = 1;  /* cell 0 has digit 1 */
    digits[1] = 0;  /* cell 1 is empty */
    uint32_t classes[81][10] = {{0}};
    elpis_grid81_build_digit_class_tensor(digits, classes);
    /* Cell 0: class 1 = 1, all others 0 */
    if (classes[0][1] != 1u) return 0;
    if (classes[0][0] != 0u) return 0;
    if (classes[0][2] != 0u) return 0;
    /* Cell 1: class 0 = 1 (empty), all others 0 */
    if (classes[1][0] != 1u) return 0;
    if (classes[1][1] != 0u) return 0;
    return 1;
}

static int test_digit_class_one_active_per_cell(void) {
    uint32_t digits[81] = {0};
    for (uint32_t i = 0; i < 81; i++) digits[i] = (i % 10);
    uint32_t classes[81][10] = {{0}};
    elpis_grid81_build_digit_class_tensor(digits, classes);
    for (uint32_t i = 0; i < 81; i++) {
        uint32_t active = 0;
        for (uint32_t j = 0; j < 10; j++) {
            if (classes[i][j] == 1u) active++;
            if (classes[i][j] > 1u) return 0;
        }
        if (active != 1u) return 0;
    }
    return 1;
}

static int test_digit_class_argmax_equals_digit(void) {
    uint32_t digits[81] = {0};
    for (uint32_t i = 0; i < 81; i++) digits[i] = (i % 10);
    uint32_t classes[81][10] = {{0}};
    elpis_grid81_build_digit_class_tensor(digits, classes);
    for (uint32_t i = 0; i < 81; i++) {
        if (classes[i][digits[i]] != 1u) return 0;
    }
    return 1;
}

static int test_occupied_mask_build(void) {
    uint32_t digits[81] = {0};
    digits[0] = 1; digits[1] = 0; digits[2] = 3;
    uint32_t mask[81] = {0};
    elpis_grid81_build_occupied_mask(digits, mask);
    return (mask[0] == 1u && mask[1] == 0u && mask[2] == 1u);
}

static int test_writable_mask_build_all_zero(void) {
    uint32_t mask[81];
    elpis_grid81_build_writable_mask(mask);
    for (uint32_t i = 0; i < 81; i++) {
        if (mask[i] != 0u) return 0;
    }
    return 1;
}

/* ========================================================================= */
/* Constraint projection tests                                               */
/* ========================================================================= */

static int test_constraint_projection_init(void) {
    elpis_semantic_grid81_constraint_projection_v1 p;
    elpis_grid81_constraint_projection_init(&p);
    return (p.abi_version == GRID81_CONSTRAINT_PROJECTION_ABI_VERSION);
}

static int test_constraint_projection_validate(void) {
    elpis_semantic_grid81_constraint_projection_v1 p;
    elpis_grid81_constraint_projection_init(&p);
    return (elpis_grid81_constraint_projection_validate(&p) == SEMANTIC_OK);
}

static int test_constraint_projection_mandatory_unsupported_blocks(void) {
    elpis_semantic_grid81_constraint_projections_v1 ps;
    elpis_grid81_constraint_projections_init(&ps);
    ps.projection_count = 1;
    elpis_grid81_constraint_projection_init(&ps.projections[0]);
    ps.projections[0].mandatory_constraint = 1;
    ps.projections[0].projection_disposition = GRID81_PROJECTION_UNSUPPORTED_BLOCKING;
    return (elpis_grid81_constraint_projections_validate(&ps) == SEMANTIC_E_INVAL);
}

static int test_constraint_projection_dispositions_exist(void) {
    /* Verify all 7 dispositions have distinct integer values 0-6 */
    return (GRID81_PROJECTION_GEOMETRICALLY_REALIZED == 0 &&
            GRID81_PROJECTION_CELL_COLOCATION_REALIZED == 1 &&
            GRID81_PROJECTION_COLUMN_SEPARATION_REALIZED == 2 &&
            GRID81_PROJECTION_ROW_STRATUM_REALIZED == 3 &&
            GRID81_PROJECTION_SIDECAR_PRESERVED == 4 &&
            GRID81_PROJECTION_TRACE_ONLY_PRESERVED == 5 &&
            GRID81_PROJECTION_UNSUPPORTED_BLOCKING == 6);
}

/* ========================================================================= */
/* Structural packet tests                                                   */
/* ========================================================================= */

static int test_structural_packet_init(void) {
    elpis_semantic_grid81_structural_packet_v1 p;
    elpis_grid81_structural_packet_init(&p);
    return (p.abi_version == GRID81_STRUCTURAL_PACKET_ABI_VERSION);
}

static int test_structural_packet_validate_empty_board(void) {
    elpis_semantic_grid81_structural_packet_v1 p;
    elpis_grid81_structural_packet_init(&p);
    /* All digits 0, all masks 0, build digit-class tensor */
    uint32_t digits[81] = {0};
    memcpy(p.grid81_digits, digits, sizeof(digits));
    elpis_grid81_build_occupied_mask(digits, p.occupied_mask81);
    elpis_grid81_build_writable_mask(p.compiler_writable_mask81);
    elpis_grid81_build_digit_class_tensor(digits, p.grid81_digit_classes);
    return (elpis_grid81_structural_packet_validate(&p) == SEMANTIC_OK);
}

static int test_structural_packet_validate_partial_board(void) {
    elpis_semantic_grid81_structural_packet_v1 p;
    elpis_grid81_structural_packet_init(&p);
    uint32_t digits[81] = {0};
    /* Set a few cells to their canonical template digits */
    digits[0] = 1; digits[4] = 5; digits[80] = 8;
    memcpy(p.grid81_digits, digits, sizeof(digits));
    elpis_grid81_build_occupied_mask(digits, p.occupied_mask81);
    elpis_grid81_build_writable_mask(p.compiler_writable_mask81);
    elpis_grid81_build_digit_class_tensor(digits, p.grid81_digit_classes);
    return (elpis_grid81_structural_packet_validate(&p) == SEMANTIC_OK);
}

static int test_structural_packet_validate_digit_out_of_range(void) {
    elpis_semantic_grid81_structural_packet_v1 p;
    elpis_grid81_structural_packet_init(&p);
    memset(p.grid81_digits, 0, sizeof(p.grid81_digits));
    p.grid81_digits[0] = 10;  /* invalid */
    elpis_grid81_build_occupied_mask(p.grid81_digits, p.occupied_mask81);
    elpis_grid81_build_writable_mask(p.compiler_writable_mask81);
    elpis_grid81_build_digit_class_tensor(p.grid81_digits, p.grid81_digit_classes);
    return (elpis_grid81_structural_packet_validate(&p) == SEMANTIC_E_INVAL);
}

static int test_structural_packet_identity_determinism(void) {
    elpis_semantic_grid81_structural_packet_v1 p1, p2;
    elpis_grid81_structural_packet_init(&p1);
    elpis_grid81_structural_packet_init(&p2);
    uint32_t digits[81] = {0};
    memcpy(p1.grid81_digits, digits, sizeof(digits));
    memcpy(p2.grid81_digits, digits, sizeof(digits));
    elpis_grid81_build_occupied_mask(digits, p1.occupied_mask81);
    elpis_grid81_build_occupied_mask(digits, p2.occupied_mask81);
    elpis_grid81_build_writable_mask(p1.compiler_writable_mask81);
    elpis_grid81_build_writable_mask(p2.compiler_writable_mask81);
    elpis_grid81_build_digit_class_tensor(digits, p1.grid81_digit_classes);
    elpis_grid81_build_digit_class_tensor(digits, p2.grid81_digit_classes);
    hacf_digest d1, d2;
    elpis_grid81_structural_packet_identity(&p1, &d1);
    elpis_grid81_structural_packet_identity(&p2, &d2);
    return (memcmp(d1.bytes, d2.bytes, HACF_DIGEST_BYTES) == 0);
}

/* ========================================================================= */
/* Compile receipt tests                                                     */
/* ========================================================================= */

static int test_compile_receipt_init(void) {
    elpis_semantic_grid81_compile_receipt_v1 r;
    elpis_grid81_compile_receipt_init(&r);
    return (r.abi_version == GRID81_COMPILE_RECEIPT_ABI_VERSION);
}

static int test_compile_receipt_qualified(void) {
    elpis_semantic_grid81_compile_receipt_v1 r;
    elpis_grid81_compile_receipt_init(&r);
    r.compile_disposition = GRID81_COMPILE_COMPLETE;
    return (elpis_grid81_compile_receipt_is_qualified(&r) == SEMANTIC_OK);
}

static int test_compile_receipt_blocked(void) {
    elpis_semantic_grid81_compile_receipt_v1 r;
    elpis_grid81_compile_receipt_init(&r);
    r.compile_disposition = GRID81_COMPILE_BLOCKED_BY_CAPACITY;
    return (elpis_grid81_compile_receipt_is_qualified(&r) == SEMANTIC_E_INVAL);
}

static int test_compile_receipt_nonzero_verification_blocks(void) {
    elpis_semantic_grid81_compile_receipt_v1 r;
    elpis_grid81_compile_receipt_init(&r);
    r.compile_disposition = GRID81_COMPILE_COMPLETE;
    r.unmapped_vertex_count = 1;
    return (elpis_grid81_compile_receipt_is_qualified(&r) == SEMANTIC_E_INVAL);
}

/* ========================================================================= */
/* Handoff tests                                                             */
/* ========================================================================= */

static int test_handoff_init(void) {
    elpis_semantic_grid81_handoff_v1 h;
    elpis_grid81_handoff_init(&h);
    if (h.abi_version != GRID81_HANDOFF_ABI_VERSION) return 0;
    if (h.handoff_kind != GRID81_TO_TRM_ADAPTER_INPUT) return 0;
    return 1;
}

static int test_handoff_boundary_flags(void) {
    elpis_semantic_grid81_handoff_v1 h;
    elpis_grid81_handoff_init(&h);
    if (!h.digits_are_sudoku_structural) return 0;
    if (!h.writable_mask_is_compiler_fixed) return 0;
    if (!h.P8_may_not_change_relation_id) return 0;
    if (!h.P8_may_not_change_authority) return 0;
    if (!h.P8_may_not_discard_conflict) return 0;
    if (!h.P8_may_not_use_adjacency_as_proof) return 0;
    if (!h.P8_may_not_invent_residual81) return 0;
    if (!h.P8_needs_separate_projector_qual) return 0;
    return 1;
}

static int test_handoff_validate(void) {
    elpis_semantic_grid81_handoff_v1 h;
    elpis_grid81_handoff_init(&h);
    return (elpis_grid81_handoff_validate(&h) == SEMANTIC_OK);
}

static int test_handoff_identity_determinism(void) {
    elpis_semantic_grid81_handoff_v1 h1, h2;
    elpis_grid81_handoff_init(&h1);
    elpis_grid81_handoff_init(&h2);
    hacf_digest d1, d2;
    elpis_grid81_handoff_identity(&h1, &d1);
    elpis_grid81_handoff_identity(&h2, &d2);
    return (memcmp(d1.bytes, d2.bytes, HACF_DIGEST_BYTES) == 0);
}

/* ========================================================================= */
/* Persistence tests                                                         */
/* ========================================================================= */

static int test_policy_persistence_roundtrip(void) {
    const char *path = "/tmp/p7_test_policy.bin";
    elpis_semantic_grid81_policy_v1 p1, p2;
    elpis_grid81_policy_init(&p1);
    if (elpis_write_grid81_policy(path, &p1) != SEMANTIC_OK) return 0;
    if (elpis_read_grid81_policy(path, &p2) != SEMANTIC_OK) return 0;
    return (p1.abi_version == p2.abi_version && p1.cell_count == p2.cell_count);
}

static int test_codebook_persistence_roundtrip(void) {
    const char *path = "/tmp/p7_test_codebook.bin";
    elpis_semantic_grid81_codebook_v1 c1, c2;
    elpis_grid81_codebook_init(&c1);
    if (elpis_write_grid81_codebook(path, &c1) != SEMANTIC_OK) return 0;
    if (elpis_read_grid81_codebook(path, &c2) != SEMANTIC_OK) return 0;
    hacf_digest d1, d2;
    elpis_grid81_codebook_identity(&c1, &d1);
    elpis_grid81_codebook_identity(&c2, &d2);
    return (memcmp(d1.bytes, d2.bytes, HACF_DIGEST_BYTES) == 0);
}

static int test_masks_persistence_roundtrip(void) {
    const char *path = "/tmp/p7_test_masks.bin";
    elpis_semantic_grid81_masks_v1 m1, m2;
    elpis_grid81_masks_init(&m1);
    if (elpis_write_grid81_masks(path, &m1) != SEMANTIC_OK) return 0;
    if (elpis_read_grid81_masks(path, &m2) != SEMANTIC_OK) return 0;
    return (memcmp(m1.compiler_writable_mask81, m2.compiler_writable_mask81,
                   sizeof(m1.compiler_writable_mask81)) == 0);
}

static int test_compile_receipt_persistence_roundtrip(void) {
    const char *path = "/tmp/p7_test_receipt.bin";
    elpis_semantic_grid81_compile_receipt_v1 r1, r2;
    elpis_grid81_compile_receipt_init(&r1);
    r1.compile_disposition = GRID81_COMPILE_COMPLETE;
    if (elpis_write_grid81_compile_receipt(path, &r1) != SEMANTIC_OK) return 0;
    if (elpis_read_grid81_compile_receipt(path, &r2) != SEMANTIC_OK) return 0;
    return (r1.compile_disposition == r2.compile_disposition);
}

static int test_handoff_persistence_roundtrip(void) {
    const char *path = "/tmp/p7_test_handoff.bin";
    elpis_semantic_grid81_handoff_v1 h1, h2;
    elpis_grid81_handoff_init(&h1);
    if (elpis_write_grid81_handoff(path, &h1) != SEMANTIC_OK) return 0;
    if (elpis_read_grid81_handoff(path, &h2) != SEMANTIC_OK) return 0;
    return (h1.handoff_kind == h2.handoff_kind &&
            h1.digits_are_sudoku_structural == h2.digits_are_sudoku_structural);
}

/* ========================================================================= */
/* Digest helper tests                                                       */
/* ========================================================================= */

static int test_zero_digest(void) {
    hacf_digest d;
    d.bytes[0] = 1;
    elpis_grid81_zero_digest(&d);
    return (d.bytes[0] == 0);
}

static int test_digest_is_zero(void) {
    hacf_digest d;
    memset(d.bytes, 0, sizeof(d.bytes));
    return (elpis_grid81_digest_is_zero(&d) == 1);
}

static int test_digest_is_not_zero(void) {
    hacf_digest d;
    memset(d.bytes, 0, sizeof(d.bytes));
    d.bytes[0] = 1;
    return (elpis_grid81_digest_is_zero(&d) == 0);
}

/* ========================================================================= */
/* Fixed-width audit tests                                                   */
/* ========================================================================= */

static int test_policy_fixed_width(void) {
    elpis_semantic_grid81_policy_v1 p;
    elpis_grid81_policy_init(&p);
    /* All fields are uint32_t or hacf_digest (uint8_t[32]) — no size_t */
    return (sizeof(p.cell_count) == 4 && sizeof(p.abi_version) == 4 &&
            sizeof(p.reserved[0]) == 1);
}

static int test_codebook_fixed_width(void) {
    grid81_codebook_entry_v1 e;
    memset(&e, 0, sizeof(e));
    return (sizeof(e) > 0 && sizeof(e.lane) == 4 && sizeof(e.column) == 4);
}

/* ========================================================================= */
/* Main                                                                      */
/* ========================================================================= */

int main(void) {
    printf("=== P7 Grid81 Structural Compiler Tests ===\n\n");

    printf("[ABI and Policy]\n");
    TEST(policy_init_and_defaults);
    TEST(policy_81_cell_contract);
    TEST(policy_10_digit_classes);
    TEST(policy_validate);
    TEST(policy_validate_null);
    TEST(policy_reserved_zeroed);
    TEST(policy_identity_determinism);
    TEST(policy_capacity_overflow_fail_closed);
    TEST(policy_writable_mask_fixed_zero);

    printf("\n[Codebook]\n");
    TEST(codebook_init_all_lanes);
    TEST(codebook_support_contradiction_distinct);
    TEST(codebook_qualifier_scope_distinct);
    TEST(codebook_unknown_lane_fails);
    TEST(codebook_identity_determinism);
    TEST(codebook_validate);
    TEST(codebook_nonauthority_flags);

    printf("\n[Sudoku Template]\n");
    TEST(sudoku_template_formula);
    TEST(sudoku_template_full_board);
    TEST(sudoku_template_validate);
    TEST(sudoku_template_digest_determinism);
    TEST(sudoku_partial_board_valid);
    TEST(sudoku_partial_board_invalid_digit);
    TEST(sudoku_constraints_valid);
    TEST(sudoku_constraints_duplicate);

    printf("\n[Capsules]\n");
    TEST(capsule_init);
    TEST(capsule_validate);
    TEST(capsule_validate_null);
    TEST(capsule_key_equality);
    TEST(capsule_key_inequality_different_lane);
    TEST(capsule_key_order);
    TEST(capsule_manifest_init);

    printf("\n[Placement]\n");
    TEST(placement_column_from_lane_only);
    TEST(placement_row_formula);
    TEST(placement_cell_range);
    TEST(placement_digit_empty);
    TEST(placement_digit_occupied);

    printf("\n[Cell Records and Masks]\n");
    TEST(cell_init);
    TEST(cell_validate_empty);
    TEST(cell_validate_occupied_agrees);
    TEST(cell_validate_writable_must_be_zero);
    TEST(masks_init_all_zero);
    TEST(masks_validate_all_zero_writable);
    TEST(masks_validate_nonzero_writable);

    printf("\n[Digit Classes]\n");
    TEST(digit_class_build);
    TEST(digit_class_one_active_per_cell);
    TEST(digit_class_argmax_equals_digit);
    TEST(occupied_mask_build);
    TEST(writable_mask_build_all_zero);

    printf("\n[Constraint Projection]\n");
    TEST(constraint_projection_init);
    TEST(constraint_projection_validate);
    TEST(constraint_projection_mandatory_unsupported_blocks);
    TEST(constraint_projection_dispositions_exist);

    printf("\n[Structural Packet]\n");
    TEST(structural_packet_init);
    TEST(structural_packet_validate_empty_board);
    TEST(structural_packet_validate_partial_board);
    TEST(structural_packet_validate_digit_out_of_range);
    TEST(structural_packet_identity_determinism);

    printf("\n[Compile Receipt]\n");
    TEST(compile_receipt_init);
    TEST(compile_receipt_qualified);
    TEST(compile_receipt_blocked);
    TEST(compile_receipt_nonzero_verification_blocks);

    printf("\n[Handoff]\n");
    TEST(handoff_init);
    TEST(handoff_boundary_flags);
    TEST(handoff_validate);
    TEST(handoff_identity_determinism);

    printf("\n[Persistence]\n");
    TEST(policy_persistence_roundtrip);
    TEST(codebook_persistence_roundtrip);
    TEST(masks_persistence_roundtrip);
    TEST(compile_receipt_persistence_roundtrip);
    TEST(handoff_persistence_roundtrip);

    printf("\n[Digest Helpers]\n");
    TEST(zero_digest);
    TEST(digest_is_zero);
    TEST(digest_is_not_zero);

    printf("\n[Fixed-Width Audit]\n");
    TEST(policy_fixed_width);

    printf("\n=== Results: %d PASS, %d FAIL (total %d) ===\n",
           tests_passed, tests_failed, tests_passed + tests_failed);

    return (tests_failed == 0) ? 0 : 1;
}
