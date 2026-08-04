/* trm_guarded_result.c — Guarded TRM result packet v1. */

#include "elpis_semantic/trm_guarded_result.h"
#include "elpis_semantic/trm_persist.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_trm_guarded_result_init(elpis_semantic_trm_guarded_result_v1 *result) {
    if (!result) return;
    memset(result, 0, sizeof(*result));
    result->abi_version = TRM_GUARDED_RESULT_VERSION;
}

/* Validate complete Sudoku board: rows, columns, 3x3 boxes.
 * Returns SEMANTIC_OK if valid (complete or valid partial). */
static int validate_sudoku_board(const uint32_t digits[GRID81_CELL_COUNT]) {
    if (!digits) return SEMANTIC_E_INVAL;

    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        if (digits[i] > 9) return SEMANTIC_E_INVAL;
    }

    /* Rows */
    for (uint32_t row = 0; row < 9; row++) {
        uint8_t seen[10] = {0};
        for (uint32_t col = 0; col < 9; col++) {
            uint32_t d = digits[row * 9 + col];
            if (d != 0) {
                if (seen[d]) return SEMANTIC_E_INVAL;
                seen[d] = 1;
            }
        }
    }

    /* Columns */
    for (uint32_t col = 0; col < 9; col++) {
        uint8_t seen[10] = {0};
        for (uint32_t row = 0; row < 9; row++) {
            uint32_t d = digits[row * 9 + col];
            if (d != 0) {
                if (seen[d]) return SEMANTIC_E_INVAL;
                seen[d] = 1;
            }
        }
    }

    /* 3x3 boxes */
    for (uint32_t br = 0; br < 3; br++) {
        for (uint32_t bc = 0; bc < 3; bc++) {
            uint8_t seen[10] = {0};
            for (uint32_t r = 0; r < 3; r++) {
                for (uint32_t c = 0; c < 3; c++) {
                    uint32_t d = digits[(br * 3 + r) * 9 + (bc * 3 + c)];
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

int elpis_trm_guarded_result_construct(
    elpis_semantic_trm_guarded_result_v1 *result,
    const uint32_t input_digits[GRID81_CELL_COUNT],
    const uint32_t guarded_digits[GRID81_CELL_COUNT],
    const uint32_t candidate_changed_mask[GRID81_CELL_COUNT],
    const uint32_t admitted_changed_mask[GRID81_CELL_COUNT],
    const uint32_t fixed_violation_mask[GRID81_CELL_COUNT],
    uint32_t candidate_changed_count,
    uint32_t admitted_changed_count,
    uint32_t fixed_violation_count,
    int sudoku_valid,
    const hacf_digest *adapter_packet_digest,
    const hacf_digest *candidate_frame_digest,
    const hacf_digest *candidate_decode_receipt_digest,
    const hacf_digest *output_guard_policy_digest,
    const hacf_digest *input_digit_array_digest,
    const hacf_digest *candidate_digit_array_digest,
    const hacf_digest *fixed_mask_digest,
    const hacf_digest *writable_mask_digest,
    const hacf_digest *candidate_changed_mask_digest,
    const hacf_digest *admitted_changed_mask_digest,
    const hacf_digest *fixed_violation_mask_digest)
{
    if (!result || !input_digits || !guarded_digits) return SEMANTIC_E_INVAL;

    elpis_trm_guarded_result_init(result);

    /* Copy digests */
    if (adapter_packet_digest)
        memcpy(&result->adapter_packet_digest, adapter_packet_digest, sizeof(hacf_digest));
    if (candidate_frame_digest)
        memcpy(&result->candidate_frame_digest, candidate_frame_digest, sizeof(hacf_digest));
    if (candidate_decode_receipt_digest)
        memcpy(&result->candidate_decode_receipt_digest, candidate_decode_receipt_digest, sizeof(hacf_digest));
    if (output_guard_policy_digest)
        memcpy(&result->output_guard_policy_digest, output_guard_policy_digest, sizeof(hacf_digest));
    if (input_digit_array_digest)
        memcpy(&result->input_digit_array_digest, input_digit_array_digest, sizeof(hacf_digest));
    if (candidate_digit_array_digest)
        memcpy(&result->candidate_digit_array_digest, candidate_digit_array_digest, sizeof(hacf_digest));
    if (fixed_mask_digest)
        memcpy(&result->fixed_mask_digest, fixed_mask_digest, sizeof(hacf_digest));
    if (writable_mask_digest)
        memcpy(&result->writable_mask_digest, writable_mask_digest, sizeof(hacf_digest));
    if (candidate_changed_mask_digest)
        memcpy(&result->candidate_changed_mask_digest, candidate_changed_mask_digest, sizeof(hacf_digest));
    if (admitted_changed_mask_digest)
        memcpy(&result->admitted_changed_mask_digest, admitted_changed_mask_digest, sizeof(hacf_digest));
    if (fixed_violation_mask_digest)
        memcpy(&result->fixed_violation_attempt_mask_digest, fixed_violation_mask_digest, sizeof(hacf_digest));

    result->candidate_changed_cell_count = candidate_changed_count;
    result->admitted_changed_cell_count = admitted_changed_count;
    result->fixed_violation_attempt_count = fixed_violation_count;

    if (!sudoku_valid) {
        /* Invalid Sudoku: return exact input board */
        result->guard_disposition = TRM_GUARDED_PROPOSAL_REJECTED_SUDOKU_INVALID;
        memcpy((void *)result->guarded_digit_array_digest.bytes, input_digits, sizeof(input_digits));
        /* Actually compute the digest of the input digits */
        elpis_trm_digest_bytes((const uint8_t *)input_digits,
            GRID81_CELL_COUNT * sizeof(uint32_t), &result->guarded_digit_array_digest);

        /* Zero admitted changes */
        memset(&result->admitted_changed_mask_digest, 0, sizeof(hacf_digest));
        result->admitted_changed_cell_count = 0;
    } else {
        /* Sudoku valid: accept guarded board */
        if (admitted_changed_count == 0) {
            result->guard_disposition = TRM_GUARDED_PROPOSAL_ACCEPTED_NO_CHANGE;
        } else {
            result->guard_disposition = TRM_GUARDED_PROPOSAL_ACCEPTED;
        }

        elpis_trm_digest_bytes((const uint8_t *)guarded_digits,
            GRID81_CELL_COUNT * sizeof(uint32_t), &result->guarded_digit_array_digest);
    }

    /* Compute guarded digit-class tensor digest from guarded digits */
    uint32_t guarded_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT];
    memset(guarded_classes, 0, sizeof(guarded_classes));
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        guarded_classes[i][guarded_digits[i]] = 1;
    }
    elpis_trm_digest_bytes((const uint8_t *)guarded_classes, sizeof(guarded_classes),
        &result->guarded_digit_class_tensor_digest);

    /* Compute Sudoku validation receipt */
    elpis_trm_digest_domain("elpis.semantic.sudoku_validation.v1", 1,
        (const uint8_t *)&sudoku_valid, sizeof(int),
        &result->Sudoku_validation_receipt_digest);

    memset(result->reserved, 0, sizeof(result->reserved));
    return SEMANTIC_OK;
}

int elpis_trm_guarded_result_identity(
    const elpis_semantic_trm_guarded_result_v1 *result, hacf_digest *out)
{
    if (!result || !out) return SEMANTIC_E_INVAL;
    return elpis_trm_digest_domain("elpis.semantic.trm_guarded_result.v1",
        result->abi_version, (const uint8_t *)result, sizeof(*result), out);
}

int elpis_trm_guarded_result_validate(const elpis_semantic_trm_guarded_result_v1 *result) {
    if (!result) return SEMANTIC_E_INVAL;
    if (result->abi_version != TRM_GUARDED_RESULT_VERSION) return SEMANTIC_E_INVAL;

    /* Disposition must be known */
    if (result->guard_disposition > TRM_GUARDED_PROPOSAL_BLOCKED_INTERNAL) {
        return SEMANTIC_E_INVAL;
    }

    for (size_t i = 0; i < sizeof(result->reserved); i++) {
        if (result->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_trm_guarded_result(const char *path, const elpis_semantic_trm_guarded_result_v1 *result) {
    if (!path || !result) return SEMANTIC_E_INVAL;
    return elpis_trm_write_binary(path, (const uint8_t *)result, (uint32_t)sizeof(*result));
}

int elpis_read_trm_guarded_result(const char *path, elpis_semantic_trm_guarded_result_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    memset(out, 0, sizeof(*out));
    uint32_t actual = 0;
    int ret = elpis_trm_read_binary(path, (uint8_t *)out, (uint32_t)sizeof(*out), &actual);
    if (ret < 0) return SEMANTIC_E_IO;
    if (actual != (uint32_t)sizeof(*out)) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}
