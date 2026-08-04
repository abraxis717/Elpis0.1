/* trm_mutability.c — TRM mutability record v1. */

#include "elpis_semantic/trm_mutability.h"
#include "elpis_semantic/trm_persist.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_trm_mutability_init(elpis_semantic_trm_mutability_v1 *mut) {
    if (!mut) return;
    memset(mut, 0, sizeof(*mut));
    mut->abi_version = TRM_MUTABILITY_VERSION;
}

int elpis_trm_mutability_derive(
    elpis_semantic_trm_mutability_v1 *mut,
    const uint32_t digits[GRID81_CELL_COUNT],
    const uint32_t occupied[GRID81_CELL_COUNT],
    const hacf_digest *P7_packet_digest,
    const hacf_digest *P7_digit_array_digest,
    const hacf_digest *P7_occupied_mask_digest,
    const hacf_digest *P7_compiler_writable_mask_digest)
{
    if (!mut || !digits || !occupied) return SEMANTIC_E_INVAL;
    if (!P7_packet_digest || !P7_digit_array_digest ||
        !P7_occupied_mask_digest || !P7_compiler_writable_mask_digest) {
        return SEMANTIC_E_INVAL;
    }

    mut->abi_version = TRM_MUTABILITY_VERSION;
    memcpy(&mut->P7_structural_packet_digest, P7_packet_digest, sizeof(hacf_digest));
    memcpy(&mut->P7_digit_array_digest, P7_digit_array_digest, sizeof(hacf_digest));
    memcpy(&mut->P7_occupied_mask_digest, P7_occupied_mask_digest, sizeof(hacf_digest));
    memcpy(&mut->P7_compiler_writable_mask_digest, P7_compiler_writable_mask_digest, sizeof(hacf_digest));

    uint32_t fixed_count = 0;
    uint32_t writable_count = 0;

    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        if (digits[i] != 0 || occupied[i] == 1) {
            mut->fixed_mask81[i] = 1;
            mut->writable_mask81[i] = 0;
            fixed_count++;
        } else {
            mut->fixed_mask81[i] = 0;
            mut->writable_mask81[i] = 1;
            writable_count++;
        }
    }

    mut->fixed_cell_count = fixed_count;
    mut->writable_cell_count = writable_count;

    if (writable_count == 0) {
        mut->disposition = TRM_MUTABILITY_NO_MUTABLE_CELLS;
    } else {
        mut->disposition = TRM_MUTABILITY_NORMAL;
    }

    /* Compute mask digests */
    elpis_trm_digest_bytes((const uint8_t *)mut->fixed_mask81,
        sizeof(mut->fixed_mask81), &mut->fixed_mask_digest);
    elpis_trm_digest_bytes((const uint8_t *)mut->writable_mask81,
        sizeof(mut->writable_mask81), &mut->writable_mask_digest);

    memset(mut->reserved, 0, sizeof(mut->reserved));
    return SEMANTIC_OK;
}

int elpis_trm_mutability_identity(const elpis_semantic_trm_mutability_v1 *mut, hacf_digest *out) {
    if (!mut || !out) return SEMANTIC_E_INVAL;
    return elpis_trm_digest_domain("elpis.semantic.trm_mutability.v1",
        mut->abi_version, (const uint8_t *)mut, sizeof(*mut), out);
}

int elpis_trm_mutability_validate(const elpis_semantic_trm_mutability_v1 *mut) {
    if (!mut) return SEMANTIC_E_INVAL;
    if (mut->abi_version != TRM_MUTABILITY_VERSION) return SEMANTIC_E_INVAL;

    uint32_t fixed_sum = 0;
    uint32_t writable_sum = 0;

    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        if (mut->fixed_mask81[i] != 0 && mut->fixed_mask81[i] != 1) return SEMANTIC_E_INVAL;
        if (mut->writable_mask81[i] != 0 && mut->writable_mask81[i] != 1) return SEMANTIC_E_INVAL;
        if (mut->fixed_mask81[i] + mut->writable_mask81[i] != 1) return SEMANTIC_E_INVAL;
        if (mut->fixed_mask81[i]) fixed_sum++;
        if (mut->writable_mask81[i]) writable_sum++;
    }

    if (fixed_sum + writable_sum != GRID81_CELL_COUNT) return SEMANTIC_E_INVAL;
    if (mut->fixed_cell_count != fixed_sum) return SEMANTIC_E_INVAL;
    if (mut->writable_cell_count != writable_sum) return SEMANTIC_E_INVAL;
    if (mut->disposition > TRM_MUTABILITY_NO_MUTABLE_CELLS) return SEMANTIC_E_INVAL;

    for (size_t i = 0; i < sizeof(mut->reserved); i++) {
        if (mut->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_trm_mutability(const char *path, const elpis_semantic_trm_mutability_v1 *mut) {
    if (!path || !mut) return SEMANTIC_E_INVAL;
    return elpis_trm_write_binary(path, (const uint8_t *)mut, (uint32_t)sizeof(*mut));
}

int elpis_read_trm_mutability(const char *path, elpis_semantic_trm_mutability_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    memset(out, 0, sizeof(*out));
    uint32_t actual = 0;
    int ret = elpis_trm_read_binary(path, (uint8_t *)out, (uint32_t)sizeof(*out), &actual);
    if (ret < 0) return SEMANTIC_E_IO;
    if (actual != (uint32_t)sizeof(*out)) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}
