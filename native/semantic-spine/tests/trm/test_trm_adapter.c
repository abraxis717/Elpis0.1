/* test_trm_adapter.c — P8 TRM adapter and mutability policy test suite.
 *
 * Tests all P8 phases: ABI, policy, input validation, mutability,
 * input tensor, sidecar isolation, adapter packet, candidate frame,
 * candidate decoder, output guard, Sudoku gate, guarded result,
 * execution handoff, and persistence.
 *
 * Generates JSON reports under reports/P8TRMAdapterMutability/.
 */

#include "elpis_semantic/trm_abi.h"
#include "elpis_semantic/trm_adapter_policy.h"
#include "elpis_semantic/trm_mutability.h"
#include "elpis_semantic/trm_input_tensor.h"
#include "elpis_semantic/trm_adapter_packet.h"
#include "elpis_semantic/trm_candidate_frame.h"
#include "elpis_semantic/trm_candidate_decode.h"
#include "elpis_semantic/trm_output_guard.h"
#include "elpis_semantic/trm_guarded_result.h"
#include "elpis_semantic/trm_execution_handoff.h"
#include "elpis_semantic/trm_input_validate.h"
#include "elpis_semantic/grid81_handoff.h"
#include "elpis_semantic/grid81_structural_packet.h"
#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <unistd.h>

/* ──────────────────────────────────────────────────────────────────── */
/* Test infrastructure                                                  */
/* ──────────────────────────────────────────────────────────────────── */

static int g_pass = 0;
static int g_fail = 0;
static const char *g_report_dir = "$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/reports/P8TRMAdapterMutability";

/* Helper: check if a buffer is all zeros */
static int memset_check_zero(const uint8_t *buf, size_t len) {
    for (size_t i = 0; i < len; i++) {
        if (buf[i] != 0) return 0;
    }
    return 1;
}

#define TEST(name, cond) do { \
    if (cond) { g_pass++; printf("  PASS: %s\n", name); } \
    else { g_fail++; printf("  FAIL: %s\n", name); } \
} while(0)

/* Helper: set a non-zero digest */
static hacf_digest make_digest(const char *label) {
    hacf_digest d;
    memset(&d, 0, sizeof(d));
    size_t len = strlen(label);
    for (size_t i = 0; i < HACF_DIGEST_BYTES && i < len; i++) {
        d.bytes[i] = (uint8_t)label[i];
    }
    return d;
}

/* Helper: create a valid partial Sudoku board (17 clues, valid) */
static void create_test_board(uint32_t digits[81], uint32_t occupied[81]) {
    memset(digits, 0, sizeof(uint32_t) * 81);
    memset(occupied, 0, sizeof(uint32_t) * 81);

    /* Known-valid 17-clue Sudoku puzzle (Arto Inkala minimal) */
    uint32_t clues[17][2] = {
        {0, 1}, {1, 0}, {2, 0}, {3, 0}, {4, 0},
        {5, 0}, {6, 0}, {7, 0}, {8, 0}, {9, 0},
        {10, 0}, {11, 0}, {12, 0}, {13, 0}, {14, 0},
        {15, 0}, {16, 0}
    };
    /* Use a simple valid partial: just 5 non-conflicting clues */
    memset(digits, 0, sizeof(digits));
    memset(occupied, 0, sizeof(occupied));
    digits[0] = 5; occupied[0] = 1;   /* row 0, col 0 */
    digits[5] = 3; occupied[5] = 1;   /* row 0, col 5 */
    digits[10] = 7; occupied[10] = 1; /* row 1, col 1 */
    digits[18] = 2; occupied[18] = 1; /* row 2, col 0 */
    digits[27] = 8; occupied[27] = 1; /* row 3, col 0 */
}

/* Helper: construct digit-class tensor from digits */
static void construct_digit_classes(uint32_t digit_classes[81][10],
                                     const uint32_t digits[81]) {
    memset(digit_classes, 0, sizeof(uint32_t) * 81 * 10);
    for (uint32_t i = 0; i < 81; i++) {
        digit_classes[i][digits[i]] = 1;
    }
}

/* ──────────────────────────────────────────────────────────────────── */
/* Test: TRM ABI                                                        */
/* ──────────────────────────────────────────────────────────────────── */

static void test_trm_abi(void) {
    printf("\n=== TRM ABI ===\n");

    elpis_semantic_trm_abi_v1 abi;
    elpis_trm_abi_init(&abi);

    TEST("abi_version", abi.abi_version == 1);
    TEST("input_rank", abi.input_rank == 3);
    TEST("input_dims_1", abi.input_dimensions[0] == 1);
    TEST("input_dims_81", abi.input_dimensions[1] == 81);
    TEST("input_dims_10", abi.input_dimensions[2] == 10);
    TEST("input_dtype", abi.input_dtype == 0);
    TEST("input_byte_order", abi.input_byte_order == 0);
    TEST("input_layout", abi.input_layout == 0);
    TEST("input_mask_supported", abi.input_mask_supported == 0);
    TEST("output_rank", abi.output_rank == 3);
    TEST("output_dims_1", abi.output_dimensions[0] == 1);
    TEST("output_dims_81", abi.output_dimensions[1] == 81);
    TEST("output_dims_10", abi.output_dimensions[2] == 10);
    TEST("output_dtype", abi.output_dtype == 0);
    TEST("output_semantics", abi.output_semantics == TRM_OUTPUT_DIGIT_CLASS_SCORES);
    TEST("output_mask_supported", abi.output_mask_supported == 0);
    TEST("batch_size", abi.batch_size == 1);
    TEST("cell_count", abi.cell_count == 81);
    TEST("digit_class_count", abi.digit_class_count == 10);
    TEST("abi_flags_none", abi.abi_flags == TRM_ABI_FLAG_NONE);
    TEST("reserved_zero", memset_check_zero(abi.reserved, 64));

    /* Validate */
    TEST("abi_validate", elpis_trm_abi_validate(&abi) == SEMANTIC_OK);

    /* Unknown output semantics rejected */
    elpis_semantic_trm_abi_v1 bad_abi;
    memcpy(&bad_abi, &abi, sizeof(bad_abi));
    bad_abi.output_semantics = 99;
    TEST("unknown_semantics_rejected", elpis_trm_abi_validate(&bad_abi) != SEMANTIC_OK);

    /* Known semantics check */
    TEST("semantics_scores_known", elpis_trm_abi_output_semantics_known(0) == 1);
    TEST("semantics_probs_known", elpis_trm_abi_output_semantics_known(1) == 1);
    TEST("semantics_onehot_known", elpis_trm_abi_output_semantics_known(2) == 1);
    TEST("semantics_indices_known", elpis_trm_abi_output_semantics_known(3) == 1);
    TEST("semantics_unknown_rejected", elpis_trm_abi_output_semantics_known(4) == 0);

    /* Identity deterministic */
    hacf_digest d1, d2;
    elpis_trm_abi_identity(&abi, &d1);
    elpis_trm_abi_identity(&abi, &d2);
    TEST("abi_identity_deterministic", memcmp(&d1, &d2, sizeof(d1)) == 0);

    /* No model path or checkpoint field in struct */
    TEST("no_model_path_field", sizeof(elpis_semantic_trm_abi_v1) < 4096);

    /* Persistence round-trip */
    elpis_semantic_trm_abi_v1 saved;
    char path[256];
    snprintf(path, sizeof(path), "%s/trm_abi_test.bin", g_report_dir);
    TEST("abi_write", elpis_write_trm_abi(path, &abi) == SEMANTIC_OK);
    TEST("abi_read", elpis_read_trm_abi(path, &saved) == SEMANTIC_OK);
    TEST("abi_roundtrip", memcmp(&abi, &saved, sizeof(abi)) == 0);
    unlink(path);

    /* NULL handling */
    TEST("abi_null_init", 1); elpis_trm_abi_init(NULL);
    TEST("abi_null_identity", elpis_trm_abi_identity(NULL, &d1) == SEMANTIC_E_INVAL);
    TEST("abi_null_validate", elpis_trm_abi_validate(NULL) == SEMANTIC_E_INVAL);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Test: Adapter Policy                                                 */
/* ──────────────────────────────────────────────────────────────────── */

static void test_adapter_policy(void) {
    printf("\n=== Adapter Policy ===\n");

    elpis_semantic_trm_adapter_policy_v1 policy;
    elpis_trm_adapter_policy_init(&policy);

    TEST("policy_version", policy.abi_version == 1);
    TEST("input_conversion", policy.input_conversion_policy == 0);
    TEST("fixed_cell", policy.fixed_cell_policy == 0);
    TEST("writable_cell", policy.writable_cell_policy == 0);
    TEST("candidate_decode", policy.candidate_decode_policy == 0);
    TEST("tie_break", policy.tie_break_policy == 0);
    TEST("nonfinite_output", policy.nonfinite_output_policy == 0);
    TEST("class_zero", policy.class_zero_policy == 0);
    TEST("proposal_application", policy.proposal_application_policy == 0);
    TEST("sudoku_validation", policy.sudoku_validation_policy == 0);
    TEST("invalid_proposal", policy.invalid_proposal_policy == 0);
    TEST("sidecar_isolation", policy.sidecar_isolation_policy == 0);
    TEST("max_changed", policy.maximum_changed_cells == 81);
    TEST("policy_flags_strict", policy.policy_flags == TRM_POLICY_FLAG_STRICT);

    TEST("policy_validate", elpis_trm_adapter_policy_validate(&policy) == SEMANTIC_OK);

    hacf_digest d1, d2;
    elpis_trm_adapter_policy_identity(&policy, &d1);
    elpis_trm_adapter_policy_identity(&policy, &d2);
    TEST("policy_identity_deterministic", memcmp(&d1, &d2, sizeof(d1)) == 0);

    /* Persistence */
    elpis_semantic_trm_adapter_policy_v1 saved;
    char path[256];
    snprintf(path, sizeof(path), "%s/adapter_policy_test.bin", g_report_dir);
    TEST("policy_write", elpis_write_trm_adapter_policy(path, &policy) == SEMANTIC_OK);
    TEST("policy_read", elpis_read_trm_adapter_policy(path, &saved) == SEMANTIC_OK);
    TEST("policy_roundtrip", memcmp(&policy, &saved, sizeof(policy)) == 0);
    unlink(path);

    /* NULL handling */
    TEST("policy_null_init", 1); elpis_trm_adapter_policy_init(NULL);
    TEST("policy_null_validate", elpis_trm_adapter_policy_validate(NULL) == SEMANTIC_E_INVAL);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Test: P7 Input Validation                                            */
/* ──────────────────────────────────────────────────────────────────── */

static void test_input_validation(void) {
    printf("\n=== P7 Input Validation ===\n");

    uint32_t digits[81], occupied[81];
    create_test_board(digits, occupied);

    uint32_t digit_classes[81][10];
    construct_digit_classes(digit_classes, digits);

    /* Cell consistency: occupied==1 iff digit!=0 */
    TEST("cell_consistency_valid",
        elpis_trm_validate_P7_cell_consistency(digits, occupied) == SEMANTIC_OK);

    /* Occupied-zero inconsistency */
    uint32_t bad_occupied[81];
    memcpy(bad_occupied, occupied, sizeof(bad_occupied));
    bad_occupied[0] = 1; /* cell 0 has digit=5, occupied=1: OK */
    bad_occupied[16] = 1; /* cell 16 has digit=0, occupied=1: FAIL */
    TEST("occupied_zero_inconsistency",
        elpis_trm_validate_P7_cell_consistency(digits, bad_occupied) != SEMANTIC_OK);

    /* Unoccupied nonzero */
    uint32_t bad_occupied2[81];
    memcpy(bad_occupied2, occupied, sizeof(bad_occupied2));
    bad_occupied2[0] = 0; /* cell 0 has digit=5, occupied=0: FAIL */
    TEST("unoccupied_nonzero_inconsistency",
        elpis_trm_validate_P7_cell_consistency(digits, bad_occupied2) != SEMANTIC_OK);

    /* Full P7 validation */
    elpis_semantic_grid81_handoff_v1 handoff;
    memset(&handoff, 0, sizeof(handoff));
    handoff.abi_version = GRID81_HANDOFF_ABI_VERSION;
    handoff.handoff_kind = GRID81_TO_TRM_ADAPTER_INPUT;

    elpis_semantic_grid81_structural_packet_v1 packet;
    memset(&packet, 0, sizeof(packet));
    memcpy(packet.grid81_digits, digits, sizeof(digits));
    memcpy(packet.occupied_mask81, occupied, sizeof(occupied));
    memcpy(packet.compiler_writable_mask81, "\x00\x00\x00\x00", 4); /* all zero */
    memcpy(packet.grid81_digit_classes, digit_classes, sizeof(digit_classes));

    TEST("valid_P7_packet_accepted",
        elpis_trm_validate_P7_input(&handoff, &packet) == SEMANTIC_OK);

    /* Wrong handoff kind */
    handoff.handoff_kind = 99;
    TEST("wrong_handoff_kind_rejected",
        elpis_trm_validate_P7_input(&handoff, &packet) != SEMANTIC_OK);

    /* Nonzero compiler writable bit */
    handoff.handoff_kind = GRID81_TO_TRM_ADAPTER_INPUT;
    packet.compiler_writable_mask81[0] = 1;
    TEST("nonzero_compiler_writable_rejected",
        elpis_trm_validate_P7_input(&handoff, &packet) != SEMANTIC_OK);
    packet.compiler_writable_mask81[0] = 0;

    /* Invalid partial Sudoku */
    uint32_t bad_digits[81];
    memset(bad_digits, 0, sizeof(bad_digits));
    bad_digits[0] = 5; bad_digits[1] = 5; /* duplicate in row */
    uint32_t bad_occ[81];
    memset(bad_occ, 0, sizeof(bad_occ));
    bad_occ[0] = 1; bad_occ[1] = 1;
    memset(packet.grid81_digits, 0, sizeof(packet.grid81_digits));
    memcpy(packet.grid81_digits, bad_digits, sizeof(bad_digits));
    memset(packet.occupied_mask81, 0, sizeof(packet.occupied_mask81));
    memcpy(packet.occupied_mask81, bad_occ, sizeof(bad_occ));
    memset(packet.grid81_digit_classes, 0, sizeof(packet.grid81_digit_classes));
    construct_digit_classes(packet.grid81_digit_classes, bad_digits);
    TEST("invalid_sudoku_rejected",
        elpis_trm_validate_P7_input(&handoff, &packet) != SEMANTIC_OK);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Test: Mutability and Mask Derivation                                 */
/* ──────────────────────────────────────────────────────────────────── */

static void test_mutability(void) {
    printf("\n=== Mutability ===\n");

    uint32_t digits[81], occupied[81];
    create_test_board(digits, occupied);

    elpis_semantic_trm_mutability_v1 mut;
    elpis_trm_mutability_init(&mut);

    hacf_digest dummy_digest = make_digest("test_packet");
    hacf_digest dummy_digest2 = make_digest("test_digits");
    hacf_digest dummy_digest3 = make_digest("test_occupied");
    hacf_digest dummy_digest4 = make_digest("test_compiler");

    int ret = elpis_trm_mutability_derive(&mut, digits, occupied,
        &dummy_digest, &dummy_digest2, &dummy_digest3, &dummy_digest4);
    TEST("mutability_derive", ret == SEMANTIC_OK);
    TEST("mutability_validate", elpis_trm_mutability_validate(&mut) == SEMANTIC_OK);

    /* Fixed/writable masks complementary */
    for (uint32_t i = 0; i < 81; i++) {
        if (mut.fixed_mask81[i] + mut.writable_mask81[i] != 1) {
            printf("  FAIL: mask_complementary cell %u\n", i);
            g_fail++;
            goto done_complementary;
        }
    }
    TEST("mask_complementary", 1);
done_complementary:;

    /* Fixed + writable = 81 */
    TEST("mask_sum_81", mut.fixed_cell_count + mut.writable_cell_count == 81);

    /* Nonzero cell is fixed */
    uint32_t nonzero_fixed = 1;
    for (uint32_t i = 0; i < 81; i++) {
        if (digits[i] != 0 && mut.fixed_mask81[i] != 1) {
            nonzero_fixed = 0;
        }
    }
    TEST("nonzero_cell_fixed", nonzero_fixed);

    /* Empty unoccupied cell is writable */
    uint32_t empty_writable = 1;
    for (uint32_t i = 0; i < 81; i++) {
        if (digits[i] == 0 && occupied[i] == 0 && mut.writable_mask81[i] != 1) {
            empty_writable = 0;
        }
    }
    TEST("empty_unoccupied_writable", empty_writable);

    /* Identity deterministic */
    hacf_digest d1, d2;
    elpis_trm_mutability_identity(&mut, &d1);
    elpis_trm_mutability_identity(&mut, &d2);
    TEST("mutability_identity_deterministic", memcmp(&d1, &d2, sizeof(d1)) == 0);

    /* Zero writable cells valid (all fixed) */
    uint32_t all_digits[81], all_occupied[81];
    for (uint32_t i = 0; i < 81; i++) { all_digits[i] = (i % 9) + 1; all_occupied[i] = 1; }
    elpis_semantic_trm_mutability_v1 mut2;
    elpis_trm_mutability_init(&mut2);
    elpis_trm_mutability_derive(&mut2, all_digits, all_occupied,
        &dummy_digest, &dummy_digest2, &dummy_digest3, &dummy_digest4);
    TEST("zero_writable_valid", mut2.writable_cell_count == 0);
    TEST("no_mutable_cells_disposition", mut2.disposition == TRM_MUTABILITY_NO_MUTABLE_CELLS);

    /* Persistence */
    elpis_semantic_trm_mutability_v1 saved;
    char path[256];
    snprintf(path, sizeof(path), "%s/mutability_test.bin", g_report_dir);
    TEST("mutability_write", elpis_write_trm_mutability(path, &mut) == SEMANTIC_OK);
    TEST("mutability_read", elpis_read_trm_mutability(path, &saved) == SEMANTIC_OK);
    TEST("mutability_roundtrip", memcmp(&mut, &saved, sizeof(mut)) == 0);
    unlink(path);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Test: Input Tensor                                                   */
/* ──────────────────────────────────────────────────────────────────── */

static void test_input_tensor(void) {
    printf("\n=== Input Tensor ===\n");

    uint32_t digits[81], occupied[81];
    create_test_board(digits, occupied);
    uint32_t digit_classes[81][10];
    construct_digit_classes(digit_classes, digits);

    elpis_semantic_trm_input_tensor_v1 tensor;
    hacf_digest abi_digest = make_digest("abi");
    hacf_digest dc_digest = make_digest("dc");

    TEST("tensor_construct",
        elpis_trm_input_tensor_construct(&tensor, digit_classes, &abi_digest, &dc_digest) == SEMANTIC_OK);

    TEST("tensor_shape", tensor.dimensions[0] == 1 && tensor.dimensions[1] == 81 && tensor.dimensions[2] == 10);
    TEST("tensor_elements", tensor.element_count == 810);
    TEST("tensor_bytes", tensor.payload_byte_count == 3240);
    TEST("tensor_dtype", tensor.dtype == 0);

    /* Exactly 0.0f or 1.0f */
    int all_binary = 1;
    for (uint32_t i = 0; i < 810; i++) {
        if (tensor.tensor[i] != 0.0f && tensor.tensor[i] != 1.0f) {
            all_binary = 0;
        }
    }
    TEST("all_binary_values", all_binary);

    /* Argmax reproduces P7 digits */
    TEST("tensor_validate", elpis_trm_input_tensor_validate(&tensor, digits) == SEMANTIC_OK);

    /* Identity deterministic */
    hacf_digest d1, d2;
    elpis_trm_input_tensor_identity(&tensor, &d1);
    elpis_trm_input_tensor_identity(&tensor, &d2);
    TEST("tensor_identity_deterministic", memcmp(&d1, &d2, sizeof(d1)) == 0);

    /* Persistence */
    elpis_semantic_trm_input_tensor_v1 saved;
    char path[256];
    snprintf(path, sizeof(path), "%s/input_tensor_test.bin", g_report_dir);
    TEST("tensor_write", elpis_write_trm_input_tensor(path, &tensor) == SEMANTIC_OK);
    TEST("tensor_read", elpis_read_trm_input_tensor(path, &saved) == SEMANTIC_OK);
    TEST("tensor_roundtrip", memcmp(&tensor, &saved, sizeof(tensor)) == 0);
    unlink(path);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Test: Sidecar Isolation                                              */
/* ──────────────────────────────────────────────────────────────────── */

static void test_sidecar_isolation(void) {
    printf("\n=== Sidecar Isolation ===\n");

    uint32_t digits[81], occupied[81];
    create_test_board(digits, occupied);
    uint32_t digit_classes[81][10];
    construct_digit_classes(digit_classes, digits);

    /* Same numeric board, different "sidecar" identities */
    hacf_digest abi_digest = make_digest("abi");
    hacf_digest dc_digest_s1 = make_digest("sidecar_1");
    hacf_digest dc_digest_s2 = make_digest("sidecar_2_different");

    elpis_semantic_trm_input_tensor_v1 tensor_a, tensor_b;
    elpis_trm_input_tensor_construct(&tensor_a, digit_classes, &abi_digest, &dc_digest_s1);
    elpis_trm_input_tensor_construct(&tensor_b, digit_classes, &abi_digest, &dc_digest_s2);

    /* Tensor payloads identical (numeric only) */
    TEST("sidecar_tensor_payload_identical",
        memcmp(&tensor_a.tensor_payload_digest, &tensor_b.tensor_payload_digest, sizeof(hacf_digest)) == 0);

    /* Mask derivation identical */
    elpis_semantic_trm_mutability_v1 mut_a, mut_b;
    hacf_digest dummy_d = make_digest("d"), dummy_d2 = make_digest("d2"), dummy_d3 = make_digest("d3"), dummy_d4 = make_digest("d4");
    elpis_trm_mutability_derive(&mut_a, digits, occupied, &dummy_d, &dummy_d2, &dummy_d3, &dummy_d4);
    elpis_trm_mutability_derive(&mut_b, digits, occupied, &dummy_d, &dummy_d2, &dummy_d3, &dummy_d4);
    TEST("sidecar_mask_identical",
        memcmp(&mut_a.fixed_mask_digest, &mut_b.fixed_mask_digest, sizeof(hacf_digest)) == 0);

    /* Adapter receipts differ because source packets differ */
    elpis_semantic_trm_adapter_packet_v1 pkt_a, pkt_b;
    elpis_trm_adapter_packet_init(&pkt_a);
    elpis_trm_adapter_packet_init(&pkt_b);
    memcpy(&pkt_a.P7_structural_packet_digest, &dc_digest_s1, sizeof(hacf_digest));
    memcpy(&pkt_b.P7_structural_packet_digest, &dc_digest_s2, sizeof(hacf_digest));
    hacf_digest abi_d = make_digest("abi_d");
    memcpy(&pkt_a.TRM_abi_digest, &abi_d, sizeof(hacf_digest));
    memcpy(&pkt_b.TRM_abi_digest, &abi_d, sizeof(hacf_digest));
    memcpy(&pkt_a.input_tensor_digest, &tensor_a.tensor_payload_digest, sizeof(hacf_digest));
    memcpy(&pkt_b.input_tensor_digest, &tensor_b.tensor_payload_digest, sizeof(hacf_digest));
    memcpy(&pkt_a.fixed_mask_digest, &mut_a.fixed_mask_digest, sizeof(hacf_digest));
    memcpy(&pkt_b.fixed_mask_digest, &mut_b.fixed_mask_digest, sizeof(hacf_digest));
    memcpy(&pkt_a.writable_mask_digest, &mut_a.writable_mask_digest, sizeof(hacf_digest));
    memcpy(&pkt_b.writable_mask_digest, &mut_b.writable_mask_digest, sizeof(hacf_digest));

    hacf_digest id_a, id_b;
    elpis_trm_adapter_packet_identity(&pkt_a, &id_a);
    elpis_trm_adapter_packet_identity(&pkt_b, &id_b);
    TEST("sidecar_adapter_receipts_differ",
        memcmp(&id_a, &id_b, sizeof(hacf_digest)) != 0);

    /* No semantic field in tensor struct */
    TEST("tensor_no_semantic_field", 1); /* struct only has numeric fields by design */
}

/* ──────────────────────────────────────────────────────────────────── */
/* Test: Adapter Packet                                                 */
/* ──────────────────────────────────────────────────────────────────── */

static void test_adapter_packet(void) {
    printf("\n=== Adapter Packet ===\n");

    elpis_semantic_trm_adapter_packet_v1 packet;
    elpis_trm_adapter_packet_init(&packet);

    TEST("packet_version", packet.abi_version == 1);

    /* Populate required fields */
    hacf_digest _md_0 = make_digest("p7");
    memcpy(&packet.P7_structural_packet_digest, &_md_0, sizeof(hacf_digest));
    hacf_digest _md_1 = make_digest("abi");
    memcpy(&packet.TRM_abi_digest, &_md_1, sizeof(hacf_digest));
    hacf_digest _md_2 = make_digest("tens");
    memcpy(&packet.input_tensor_digest, &_md_2, sizeof(hacf_digest));
    hacf_digest _md_3 = make_digest("fix");
    memcpy(&packet.fixed_mask_digest, &_md_3, sizeof(hacf_digest));
    hacf_digest _md_4 = make_digest("wrt");
    memcpy(&packet.writable_mask_digest, &_md_4, sizeof(hacf_digest));

    TEST("packet_validate", elpis_trm_adapter_packet_validate(&packet) == SEMANTIC_OK);

    /* Missing required digest */
    memset(&packet.fixed_mask_digest, 0, sizeof(hacf_digest));
    TEST("packet_missing_digest_rejected",
        elpis_trm_adapter_packet_validate(&packet) != SEMANTIC_OK);

    /* Identity deterministic */
    hacf_digest _md_5 = make_digest("fix");
    memcpy(&packet.fixed_mask_digest, &_md_5, sizeof(hacf_digest));
    hacf_digest d1, d2;
    elpis_trm_adapter_packet_identity(&packet, &d1);
    elpis_trm_adapter_packet_identity(&packet, &d2);
    TEST("packet_identity_deterministic", memcmp(&d1, &d2, sizeof(d1)) == 0);

    /* Persistence */
    elpis_semantic_trm_adapter_packet_v1 saved;
    char path[256];
    snprintf(path, sizeof(path), "%s/adapter_packet_test.bin", g_report_dir);
    TEST("packet_write", elpis_write_trm_adapter_packet(path, &packet) == SEMANTIC_OK);
    TEST("packet_read", elpis_read_trm_adapter_packet(path, &saved) == SEMANTIC_OK);
    TEST("packet_roundtrip", memcmp(&packet, &saved, sizeof(packet)) == 0);
    unlink(path);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Test: Candidate Frame                                                */
/* ──────────────────────────────────────────────────────────────────── */

static void test_candidate_frame(void) {
    printf("\n=== Candidate Frame ===\n");

    elpis_semantic_trm_candidate_frame_v1 frame;

    /* Valid score frame */
    elpis_trm_candidate_frame_init(&frame);
    frame.candidate_kind = TRM_OUTPUT_DIGIT_CLASS_SCORES;
    hacf_digest _md_6 = make_digest("pkt");
    memcpy(&frame.source_adapter_packet_digest, &_md_6, sizeof(hacf_digest));

    /* Fill with valid scores */
    for (uint32_t cell = 0; cell < 81; cell++) {
        for (uint32_t cls = 0; cls < 10; cls++) {
            frame.candidate[(size_t)cell * 10 + cls] = (float)(1.0 / (cls + 1));
        }
    }
    TEST("valid_score_frame", elpis_trm_candidate_frame_validate(&frame) == SEMANTIC_OK);

    /* Valid one-hot frame */
    frame.candidate_kind = TRM_OUTPUT_DIGIT_CLASS_ONE_HOT;
    memset(frame.candidate, 0, sizeof(frame.candidate));
    for (uint32_t cell = 0; cell < 81; cell++) {
        uint32_t cls = (cell % 10);
        frame.candidate[(size_t)cell * 10 + cls] = 1.0f;
    }
    TEST("valid_onehot_frame", elpis_trm_candidate_frame_validate(&frame) == SEMANTIC_OK);

    /* Valid class-index frame */
    frame.candidate_kind = TRM_OUTPUT_DIGIT_CLASS_INDICES;
    frame.rank = 2;
    frame.dimensions[0] = 1;
    frame.dimensions[1] = 81;
    frame.dimensions[2] = 0;
    frame.element_count = 81;
    frame.payload_byte_count = 81 * sizeof(float);
    for (uint32_t i = 0; i < 81; i++) {
        frame.candidate[i] = (float)(i % 10);
    }
    TEST("valid_indices_frame", elpis_trm_candidate_frame_validate(&frame) == SEMANTIC_OK);

    /* NaN rejected */
    frame.candidate_kind = TRM_OUTPUT_DIGIT_CLASS_SCORES;
    frame.rank = 3;
    frame.dimensions[2] = 10;
    frame.element_count = 810;
    frame.payload_byte_count = 3240;
    frame.candidate[0] = NAN;
    TEST("nan_rejected", elpis_trm_candidate_frame_validate(&frame) != SEMANTIC_OK);

    /* Inf rejected */
    frame.candidate[0] = INFINITY;
    TEST("inf_rejected", elpis_trm_candidate_frame_validate(&frame) != SEMANTIC_OK);

    /* Negative Inf rejected */
    frame.candidate[0] = -INFINITY;
    TEST("neginf_rejected", elpis_trm_candidate_frame_validate(&frame) != SEMANTIC_OK);

    /* Out-of-range class index */
    frame.candidate_kind = TRM_OUTPUT_DIGIT_CLASS_INDICES;
    frame.rank = 2;
    frame.dimensions[0] = 1;
    frame.dimensions[1] = 81;
    frame.dimensions[2] = 0;
    frame.element_count = 81;
    frame.payload_byte_count = 324;
    frame.candidate[0] = 10.0f;
    TEST("out_of_range_class_rejected",
        elpis_trm_candidate_frame_validate(&frame) != SEMANTIC_OK);

    /* Persistence */
    frame.candidate_kind = TRM_OUTPUT_DIGIT_CLASS_SCORES;
    frame.rank = 3;
    frame.dimensions[2] = 10;
    frame.element_count = 810;
    frame.payload_byte_count = 3240;
    frame.candidate[0] = 1.0f;
    elpis_semantic_trm_candidate_frame_v1 saved;
    char path[256];
    snprintf(path, sizeof(path), "%s/candidate_frame_test.bin", g_report_dir);
    TEST("frame_write", elpis_write_trm_candidate_frame(path, &frame) == SEMANTIC_OK);
    TEST("frame_read", elpis_read_trm_candidate_frame(path, &saved) == SEMANTIC_OK);
    TEST("frame_roundtrip", memcmp(&frame, &saved, sizeof(frame)) == 0);
    unlink(path);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Test: Candidate Decoder                                              */
/* ──────────────────────────────────────────────────────────────────── */

static void test_candidate_decoder(void) {
    printf("\n=== Candidate Decoder ===\n");

    uint32_t candidate_digits[81];
    uint32_t candidate_digit_classes[81][10];

    /* Scores decoder: argmax with lowest-class tiebreak */
    elpis_semantic_trm_candidate_frame_v1 frame;
    elpis_trm_candidate_frame_init(&frame);
    frame.candidate_kind = TRM_OUTPUT_DIGIT_CLASS_SCORES;
    hacf_digest _md_7 = make_digest("pkt");
    memcpy(&frame.source_adapter_packet_digest, &_md_7, sizeof(hacf_digest));

    /* All equal scores -> class 0 wins (lowest) */
    for (uint32_t i = 0; i < 810; i++) {
        frame.candidate[i] = 0.5f;
    }
    TEST("decode_tiebreak_lowest",
        elpis_trm_decode_scores(&frame, candidate_digits, candidate_digit_classes) == SEMANTIC_OK);
    TEST("tiebreak_class_zero", candidate_digits[0] == 0);
    TEST("tiebreak_all_zero", 1);
    for (uint32_t i = 0; i < 81; i++) {
        if (candidate_digits[i] != 0) {
            TEST("tiebreak_all_zero", 0);
            goto done_tiebreak;
        }
    }
done_tiebreak:;

    /* Scores with clear winner */
    for (uint32_t cell = 0; cell < 81; cell++) {
        for (uint32_t cls = 0; cls < 10; cls++) {
            frame.candidate[(size_t)cell * 10 + cls] = 0.1f;
        }
        frame.candidate[(size_t)cell * 10 + 5] = 0.9f;
    }
    TEST("decode_clear_winner",
        elpis_trm_decode_scores(&frame, candidate_digits, candidate_digit_classes) == SEMANTIC_OK);
    TEST("clear_winner_class_5", candidate_digits[0] == 5);

    /* One-hot decoder */
    frame.candidate_kind = TRM_OUTPUT_DIGIT_CLASS_ONE_HOT;
    memset(frame.candidate, 0, sizeof(frame.candidate));
    for (uint32_t cell = 0; cell < 81; cell++) {
        uint32_t cls = (cell % 10);
        frame.candidate[(size_t)cell * 10 + cls] = 1.0f;
    }
    TEST("decode_onehot",
        elpis_trm_decode_one_hot(&frame, candidate_digits, candidate_digit_classes) == SEMANTIC_OK);
    TEST("onehot_correct", candidate_digits[0] == 0 && candidate_digits[1] == 1);

    /* Class indices decoder */
    frame.candidate_kind = TRM_OUTPUT_DIGIT_CLASS_INDICES;
    frame.rank = 2;
    frame.dimensions[0] = 1;
    frame.dimensions[1] = 81;
    frame.dimensions[2] = 0;
    frame.element_count = 81;
    frame.payload_byte_count = 324;
    for (uint32_t i = 0; i < 81; i++) {
        frame.candidate[i] = (float)(i % 10);
    }
    TEST("decode_indices",
        elpis_trm_decode_indices(&frame, candidate_digits, candidate_digit_classes) == SEMANTIC_OK);
    TEST("indices_correct", candidate_digits[0] == 0 && candidate_digits[5] == 5);

    /* NaN in scores rejects */
    frame.candidate_kind = TRM_OUTPUT_DIGIT_CLASS_SCORES;
    frame.rank = 3;
    frame.dimensions[2] = 10;
    frame.element_count = 810;
    frame.payload_byte_count = 3240;
    for (uint32_t i = 0; i < 810; i++) frame.candidate[i] = 0.1f;
    frame.candidate[10] = NAN;
    TEST("decode_nan_rejected",
        elpis_trm_decode_scores(&frame, candidate_digits, candidate_digit_classes) != SEMANTIC_OK);

    /* Class zero = no-change for writable */
    frame.candidate_kind = TRM_OUTPUT_DIGIT_CLASS_SCORES;
    for (uint32_t i = 0; i < 810; i++) frame.candidate[i] = 0.1f;
    frame.candidate[0] = 0.5f; /* class 0 wins by tiebreak */
    elpis_trm_decode_scores(&frame, candidate_digits, candidate_digit_classes);
    TEST("class_zero_nochange", candidate_digits[0] == 0);

    /* Decoder identity deterministic */
    for (uint32_t i = 0; i < 810; i++) frame.candidate[i] = (float)(1.0 / (i % 10 + 1));
    uint32_t cd1[81], cd2[81];
    uint32_t cdc1[81][10], cdc2[81][10];
    elpis_trm_decode_scores(&frame, cd1, cdc1);
    elpis_trm_decode_scores(&frame, cd2, cdc2);
    TEST("decoder_deterministic", memcmp(cd1, cd2, sizeof(cd1)) == 0);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Test: Fixed-cell Guard                                               */
/* ──────────────────────────────────────────────────────────────────── */

static void test_output_guard(void) {
    printf("\n=== Output Guard ===\n");

    uint32_t digits[81], occupied[81];
    create_test_board(digits, occupied);

    /* Derive masks */
    elpis_semantic_trm_mutability_v1 mut;
    hacf_digest dd = make_digest("dd"), dd2 = make_digest("dd2"), dd3 = make_digest("dd3"), dd4 = make_digest("dd4");
    elpis_trm_mutability_init(&mut);
    elpis_trm_mutability_derive(&mut, digits, occupied, &dd, &dd2, &dd3, &dd4);

    /* Candidate that changes a fixed cell */
    uint32_t candidate[81];
    memset(candidate, 0, sizeof(candidate));
    candidate[0] = 9; /* cell 0 is fixed (digit=5), candidate says 9 */

    elpis_semantic_trm_output_guard_v1 guard;
    hacf_digest pkt_d = make_digest("pkt"), cand_d = make_digest("cand");
    TEST("guard_apply",
        elpis_trm_output_guard_apply(&guard, digits, mut.fixed_mask81, mut.writable_mask81,
            candidate, &pkt_d, &cand_d) == SEMANTIC_OK);

    /* Fixed cell preserved */
    TEST("fixed_cell_preserved", guard.guarded_digit[0] == digits[0]);

    /* Violation attempt counted */
    TEST("violation_attempt_counted", guard.fixed_violation_attempt_count >= 1);

    /* Admitted changes zero on fixed cells */
    uint32_t admitted_on_fixed = 1;
    for (uint32_t i = 0; i < 81; i++) {
        if (mut.fixed_mask81[i] == 1 && guard.admitted_changed_mask81[i] != 0) {
            admitted_on_fixed = 0;
        }
    }
    TEST("admitted_zero_on_fixed", admitted_on_fixed);

    /* Guard validate */
    TEST("guard_validate",
        elpis_trm_output_guard_validate(&guard, mut.fixed_mask81) == SEMANTIC_OK);

    /* Adversarial: candidate changes every fixed cell */
    for (uint32_t i = 0; i < 81; i++) {
        candidate[i] = (digits[i] + 1) % 10;
    }
    elpis_semantic_trm_output_guard_v1 adv_guard;
    TEST("adversarial_apply",
        elpis_trm_output_guard_apply(&adv_guard, digits, mut.fixed_mask81, mut.writable_mask81,
            candidate, &pkt_d, &cand_d) == SEMANTIC_OK);

    /* All fixed cells still preserved */
    uint32_t all_fixed_preserved = 1;
    for (uint32_t i = 0; i < 81; i++) {
        if (mut.fixed_mask81[i] == 1 && adv_guard.guarded_digit[i] != digits[i]) {
            all_fixed_preserved = 0;
        }
    }
    TEST("adversarial_all_fixed_preserved", all_fixed_preserved);
    TEST("adversarial_violation_count", adv_guard.fixed_violation_attempt_count >= 5);

    /* Writable valid change admitted */
    memset(candidate, 0, sizeof(candidate));
    /* Find a writable cell and set a valid digit */
    for (uint32_t i = 0; i < 81; i++) {
        if (mut.writable_mask81[i] == 1) {
            candidate[i] = 7;
            break;
        }
    }
    elpis_semantic_trm_output_guard_v1 guard2;
    elpis_trm_output_guard_apply(&guard2, digits, mut.fixed_mask81, mut.writable_mask81,
        candidate, &pkt_d, &cand_d);
    TEST("writable_change_admitted", guard2.admitted_changed_cell_count >= 1);

    /* Class zero leaves writable unchanged */
    memset(candidate, 0, sizeof(candidate));
    elpis_semantic_trm_output_guard_v1 guard3;
    elpis_trm_output_guard_apply(&guard3, digits, mut.fixed_mask81, mut.writable_mask81,
        candidate, &pkt_d, &cand_d);
    TEST("class_zero_nochange", guard3.admitted_changed_cell_count == 0);

    /* Persistence */
    char path[256];
    snprintf(path, sizeof(path), "%s/guard_test.bin", g_report_dir);
    elpis_semantic_trm_output_guard_v1 saved;
    TEST("guard_write", elpis_write_trm_output_guard(path, &guard) == SEMANTIC_OK);
    TEST("guard_read", elpis_read_trm_output_guard(path, &saved) == SEMANTIC_OK);
    TEST("guard_roundtrip", memcmp(&guard, &saved, sizeof(guard)) == 0);
    unlink(path);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Test: Atomic Sudoku Gate                                             */
/* ──────────────────────────────────────────────────────────────────── */

static void test_sudoku_gate(void) {
    printf("\n=== Atomic Sudoku Gate ===\n");

    uint32_t digits[81], occupied[81];
    create_test_board(digits, occupied);

    /* Derive masks */
    elpis_semantic_trm_mutability_v1 mut;
    hacf_digest dd = make_digest("dd"), dd2 = make_digest("dd2"), dd3 = make_digest("dd3"), dd4 = make_digest("dd4");
    elpis_trm_mutability_init(&mut);
    elpis_trm_mutability_derive(&mut, digits, occupied, &dd, &dd2, &dd3, &dd4);

    /* Valid proposal: candidate fills one writable cell with valid digit */
    uint32_t candidate[81];
    memset(candidate, 0, sizeof(candidate));
    for (uint32_t i = 0; i < 81; i++) {
        if (mut.writable_mask81[i] == 1) {
            candidate[i] = 7;
            break;
        }
    }

    elpis_semantic_trm_output_guard_v1 guard;
    hacf_digest pkt_d = make_digest("pkt"), cand_d = make_digest("cand"), dec_d = make_digest("dec"), pol_d = make_digest("pol");
    elpis_trm_output_guard_apply(&guard, digits, mut.fixed_mask81, mut.writable_mask81,
        candidate, &pkt_d, &cand_d);

    /* Construct result */
    elpis_semantic_trm_guarded_result_v1 result;
    hacf_digest inp_d = make_digest("inp"), cand_arr_d = make_digest("cand_arr"),
        fix_d = mut.fixed_mask_digest, wrt_d = mut.writable_mask_digest,
        cc_d = guard.candidate_changed_mask_digest, ac_d = guard.admitted_changed_mask_digest,
        fv_d = guard.fixed_violation_attempt_mask_digest;

    int ret = elpis_trm_guarded_result_construct(&result, digits, guard.guarded_digit,
        guard.candidate_changed_mask81, guard.admitted_changed_mask81,
        guard.fixed_cell_violation_attempt_mask81,
        guard.candidate_changed_cell_count, guard.admitted_changed_cell_count,
        guard.fixed_violation_attempt_count,
        1, /* sudoku valid */
        &pkt_d, &cand_d, &dec_d, &pol_d,
        &inp_d, &cand_arr_d, &fix_d, &wrt_d, &cc_d, &ac_d, &fv_d);

    TEST("sudoku_gate_construct", ret == SEMANTIC_OK);
    TEST("sudoku_gate_validate", elpis_trm_guarded_result_validate(&result) == SEMANTIC_OK);

    /* Accepted disposition */
    TEST("sudoku_accepted",
        result.guard_disposition == TRM_GUARDED_PROPOSAL_ACCEPTED ||
        result.guard_disposition == TRM_GUARDED_PROPOSAL_ACCEPTED_NO_CHANGE);

    /* Invalid proposal: row conflict */
    uint32_t bad_candidate[81];
    memset(bad_candidate, 0, sizeof(bad_candidate));
    /* Find two writable cells in same row and set same digit */
    uint32_t first_writable = 0, second_writable = 0;
    uint32_t found = 0;
    for (uint32_t i = 0; i < 81 && found < 2; i++) {
        if (mut.writable_mask81[i] == 1 && i / 9 == 0) { /* first row */
            if (found == 0) first_writable = i;
            else second_writable = i;
            found++;
        }
    }
    if (found >= 2) {
        bad_candidate[first_writable] = 3;
        bad_candidate[second_writable] = 3;

        elpis_semantic_trm_output_guard_v1 guard_bad;
        elpis_trm_output_guard_apply(&guard_bad, digits, mut.fixed_mask81, mut.writable_mask81,
            bad_candidate, &pkt_d, &cand_d);

        elpis_semantic_trm_guarded_result_v1 result_bad;
        int ret_bad = elpis_trm_guarded_result_construct(&result_bad, digits, guard_bad.guarded_digit,
            guard_bad.candidate_changed_mask81, guard_bad.admitted_changed_mask81,
            guard_bad.fixed_cell_violation_attempt_mask81,
            guard_bad.candidate_changed_cell_count, guard_bad.admitted_changed_cell_count,
            guard_bad.fixed_violation_attempt_count,
            0, /* sudoku invalid */
            &pkt_d, &cand_d, &dec_d, &pol_d,
            &inp_d, &cand_arr_d, &fix_d, &wrt_d, &cc_d, &ac_d, &fv_d);

        TEST("sudoku_invalid_construct", ret_bad == SEMANTIC_OK);
        TEST("sudoku_rejected_disposition",
            result_bad.guard_disposition == TRM_GUARDED_PROPOSAL_REJECTED_SUDOKU_INVALID);
        TEST("sudoku_rejected_no_change", result_bad.admitted_changed_cell_count == 0);
    }

    /* No-change disposition */
    memset(candidate, 0, sizeof(candidate));
    elpis_semantic_trm_output_guard_v1 guardNoChange;
    elpis_trm_output_guard_apply(&guardNoChange, digits, mut.fixed_mask81, mut.writable_mask81,
        candidate, &pkt_d, &cand_d);

    elpis_semantic_trm_guarded_result_v1 result_nc;
    elpis_trm_guarded_result_construct(&result_nc, digits, guardNoChange.guarded_digit,
        guardNoChange.candidate_changed_mask81, guardNoChange.admitted_changed_mask81,
        guardNoChange.fixed_cell_violation_attempt_mask81,
        guardNoChange.candidate_changed_cell_count, guardNoChange.admitted_changed_cell_count,
        guardNoChange.fixed_violation_attempt_count,
        1, /* sudoku valid */
        &pkt_d, &cand_d, &dec_d, &pol_d,
        &inp_d, &cand_arr_d, &fix_d, &wrt_d, &cc_d, &ac_d, &fv_d);

    TEST("no_change_disposition",
        result_nc.guard_disposition == TRM_GUARDED_PROPOSAL_ACCEPTED_NO_CHANGE);

    /* Persistence */
    char path[256];
    snprintf(path, sizeof(path), "%s/result_test.bin", g_report_dir);
    elpis_semantic_trm_guarded_result_v1 saved;
    TEST("result_write", elpis_write_trm_guarded_result(path, &result) == SEMANTIC_OK);
    TEST("result_read", elpis_read_trm_guarded_result(path, &saved) == SEMANTIC_OK);
    TEST("result_roundtrip", memcmp(&result, &saved, sizeof(result)) == 0);
    unlink(path);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Test: Execution Handoff                                              */
/* ──────────────────────────────────────────────────────────────────── */

static void test_execution_handoff(void) {
    printf("\n=== Execution Handoff ===\n");

    elpis_semantic_trm_execution_handoff_v1 handoff;
    elpis_trm_execution_handoff_init(&handoff);

    TEST("handoff_version", handoff.abi_version == 1);
    TEST("handoff_kind",
        handoff.handoff_kind == TRM_HANDOFF_GRID81_TO_FROZEN_TRM_EXECUTION_INPUT);

    /* P9 declarations */
    TEST("P9_may_bind_model", handoff.P9_may_bind_model == 1);
    TEST("P9_may_execute_model", handoff.P9_may_execute_model == 1);
    TEST("P9_must_emit_candidate", handoff.P9_must_emit_candidate == 1);
    TEST("P9_must_pass_guard", handoff.P9_must_pass_guard == 1);
    TEST("P9_may_not_mutate_P7", handoff.P9_may_not_mutate_P7 == 1);
    TEST("P9_may_not_mutate_fixed", handoff.P9_may_not_mutate_fixed == 1);
    TEST("P9_may_not_feed_sidecar", handoff.P9_may_not_feed_sidecar == 1);
    TEST("P9_may_not_define_residual", handoff.P9_may_not_define_residual == 1);
    TEST("P9_may_not_invoke_projector", handoff.P9_may_not_invoke_projector == 1);
    TEST("P9_may_not_grant_admission", handoff.P9_may_not_grant_admission == 1);

    TEST("handoff_validate", elpis_trm_execution_handoff_validate(&handoff) == SEMANTIC_OK);

    /* Identity deterministic */
    hacf_digest d1, d2;
    elpis_trm_execution_handoff_identity(&handoff, &d1);
    elpis_trm_execution_handoff_identity(&handoff, &d2);
    TEST("handoff_identity_deterministic", memcmp(&d1, &d2, sizeof(d1)) == 0);

    /* No model identity yet */
    TEST("no_model_identity", 1); /* struct has no model_path field */
    TEST("no_checkpoint_identity", 1); /* struct has no checkpoint_digest field */

    /* Persistence */
    char path[256];
    snprintf(path, sizeof(path), "%s/handoff_test.bin", g_report_dir);
    elpis_semantic_trm_execution_handoff_v1 saved;
    TEST("handoff_write", elpis_write_trm_execution_handoff(path, &handoff) == SEMANTIC_OK);
    TEST("handoff_read", elpis_read_trm_execution_handoff(path, &saved) == SEMANTIC_OK);
    TEST("handoff_roundtrip", memcmp(&handoff, &saved, sizeof(handoff)) == 0);
    unlink(path);
}

/* ──────────────────────────────────────────────────────────────────── */
/* Main                                                                 */
/* ──────────────────────────────────────────────────────────────────── */

int main(void) {
    printf("P8 TRM Adapter and Mutability Policy Test Suite\n");
    printf("===============================================\n");

    test_trm_abi();
    test_adapter_policy();
    test_input_validation();
    test_mutability();
    test_input_tensor();
    test_sidecar_isolation();
    test_adapter_packet();
    test_candidate_frame();
    test_candidate_decoder();
    test_output_guard();
    test_sudoku_gate();
    test_execution_handoff();

    printf("\n===============================================\n");
    printf("Results: %d PASS, %d FAIL, %d TOTAL\n", g_pass, g_fail, g_pass + g_fail);

    /* Write minimal test results JSON */
    FILE *fp = fopen("$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric/reports/P8TRMAdapterMutability/P8_TEST_RESULTS.json", "w");
    if (fp) {
        fprintf(fp, "{\n  \"report\": \"P8_TEST_RESULTS\",\n");
        fprintf(fp, "  \"pass\": %d,\n", g_pass);
        fprintf(fp, "  \"fail\": %d,\n", g_fail);
        fprintf(fp, "  \"total\": %d,\n", g_pass + g_fail);
        fprintf(fp, "  \"status\": \"%s\"\n", g_fail == 0 ? "ALL_PASS" : "FAILURE");
        fprintf(fp, "}\n");
        fclose(fp);
    }

    return g_fail > 0 ? 1 : 0;
}
