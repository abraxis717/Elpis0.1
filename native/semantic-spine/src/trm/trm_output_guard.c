/* trm_output_guard.c — Fail-closed TRM output guard v1. */

#include "elpis_semantic/trm_output_guard.h"
#include "elpis_semantic/trm_persist.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_trm_output_guard_init(elpis_semantic_trm_output_guard_v1 *guard) {
    if (!guard) return;
    memset(guard, 0, sizeof(*guard));
    guard->abi_version = TRM_OUTPUT_GUARD_VERSION;
}

int elpis_trm_output_guard_apply(
    elpis_semantic_trm_output_guard_v1 *guard,
    const uint32_t input_digits[GRID81_CELL_COUNT],
    const uint32_t fixed_mask[GRID81_CELL_COUNT],
    const uint32_t writable_mask[GRID81_CELL_COUNT],
    const uint32_t candidate_digits[GRID81_CELL_COUNT],
    const hacf_digest *adapter_packet_digest,
    const hacf_digest *candidate_frame_digest)
{
    if (!guard || !input_digits || !fixed_mask || !writable_mask || !candidate_digits) {
        return SEMANTIC_E_INVAL;
    }
    if (!adapter_packet_digest || !candidate_frame_digest) return SEMANTIC_E_INVAL;

    elpis_trm_output_guard_init(guard);

    memcpy(&guard->adapter_packet_digest, adapter_packet_digest, sizeof(hacf_digest));
    memcpy(&guard->candidate_frame_digest, candidate_frame_digest, sizeof(hacf_digest));

    uint32_t candidate_changed_count = 0;
    uint32_t admitted_changed_count = 0;
    uint32_t fixed_violation_count = 0;

    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        /* Fixed cell: preserve input, check for violation attempt */
        if (fixed_mask[i] == 1) {
            guard->guarded_digit[i] = input_digits[i];
            guard->candidate_changed_mask81[i] = (candidate_digits[i] != input_digits[i]) ? 1 : 0;
            guard->admitted_changed_mask81[i] = 0;
            guard->fixed_cell_violation_attempt_mask81[i] =
                (candidate_digits[i] != input_digits[i]) ? 1 : 0;

            if (candidate_digits[i] != input_digits[i]) {
                candidate_changed_count++;
                fixed_violation_count++;
            }
        }
        /* Writable cell: apply policy */
        else if (writable_mask[i] == 1) {
            guard->candidate_changed_mask81[i] = (candidate_digits[i] != input_digits[i]) ? 1 : 0;

            if (candidate_digits[i] == 0) {
                /* Class zero = no change for writable cell */
                guard->guarded_digit[i] = input_digits[i];
                guard->admitted_changed_mask81[i] = 0;
            } else if (candidate_digits[i] >= 1 && candidate_digits[i] <= 9) {
                /* Admit change */
                guard->guarded_digit[i] = candidate_digits[i];
                guard->admitted_changed_mask81[i] = (candidate_digits[i] != input_digits[i]) ? 1 : 0;
                if (candidate_digits[i] != input_digits[i]) {
                    candidate_changed_count++;
                    admitted_changed_count++;
                }
            } else {
                /* Invalid candidate digit for writable cell — treat as no change */
                guard->guarded_digit[i] = input_digits[i];
                guard->admitted_changed_mask81[i] = 0;
            }
            guard->fixed_cell_violation_attempt_mask81[i] = 0;
        } else {
            /* Neither fixed nor writable — should not happen */
            guard->guarded_digit[i] = input_digits[i];
            guard->candidate_changed_mask81[i] = 0;
            guard->admitted_changed_mask81[i] = 0;
            guard->fixed_cell_violation_attempt_mask81[i] = 0;
        }
    }

    guard->candidate_changed_cell_count = candidate_changed_count;
    guard->admitted_changed_cell_count = admitted_changed_count;
    guard->fixed_violation_attempt_count = fixed_violation_count;
    guard->disposition = TRM_GUARD_CONTINUE_TO_SUDOKU_GATE;

    /* Compute change mask digests */
    elpis_trm_digest_bytes((const uint8_t *)guard->candidate_changed_mask81,
        sizeof(guard->candidate_changed_mask81), &guard->candidate_changed_mask_digest);
    elpis_trm_digest_bytes((const uint8_t *)guard->admitted_changed_mask81,
        sizeof(guard->admitted_changed_mask81), &guard->admitted_changed_mask_digest);
    elpis_trm_digest_bytes((const uint8_t *)guard->fixed_cell_violation_attempt_mask81,
        sizeof(guard->fixed_cell_violation_attempt_mask81),
        &guard->fixed_violation_attempt_mask_digest);

    memset(guard->reserved, 0, sizeof(guard->reserved));
    return SEMANTIC_OK;
}

int elpis_trm_output_guard_validate(
    const elpis_semantic_trm_output_guard_v1 *guard,
    const uint32_t fixed_mask[GRID81_CELL_COUNT])
{
    if (!guard) return SEMANTIC_E_INVAL;
    if (guard->abi_version != TRM_OUTPUT_GUARD_VERSION) return SEMANTIC_E_INVAL;
    if (guard->disposition > TRM_GUARD_BLOCKED_INTERNAL) return SEMANTIC_E_INVAL;

    /* Admitted changes must be zero on fixed cells */
    if (fixed_mask) {
        for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
            if (fixed_mask[i] == 1 && guard->admitted_changed_mask81[i] != 0) {
                return SEMANTIC_E_INVAL;
            }
        }
    }

    for (size_t i = 0; i < sizeof(guard->reserved); i++) {
        if (guard->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_trm_output_guard(const char *path, const elpis_semantic_trm_output_guard_v1 *guard) {
    if (!path || !guard) return SEMANTIC_E_INVAL;
    return elpis_trm_write_binary(path, (const uint8_t *)guard, (uint32_t)sizeof(*guard));
}

int elpis_read_trm_output_guard(const char *path, elpis_semantic_trm_output_guard_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    memset(out, 0, sizeof(*out));
    uint32_t actual = 0;
    int ret = elpis_trm_read_binary(path, (uint8_t *)out, (uint32_t)sizeof(*out), &actual);
    if (ret < 0) return SEMANTIC_E_IO;
    if (actual != (uint32_t)sizeof(*out)) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}
