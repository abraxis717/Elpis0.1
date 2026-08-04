/* grid81_persist.c — P7 persistence and serialization helpers. */
#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/grid81_codebook.h"
#include "elpis_semantic/grid81_capsule.h"
#include "elpis_semantic/grid81_cell.h"
#include "elpis_semantic/grid81_constraint_projection.h"
#include "elpis_semantic/grid81_structural_packet.h"
#include "elpis_semantic/grid81_compile_receipt.h"
#include "elpis_semantic/grid81_handoff.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>

/* Compute digest from raw bytes. Domain is a string label. */
int elpis_grid81_digest_bytes(
    const char *domain, const uint8_t *data, size_t len, hacf_digest *out) {
    if (!domain || !data || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    elpis_sha256_update(&ctx, (const uint8_t *)domain, 4);
    elpis_sha256_update(&ctx, data, len);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

/* Compute digit array digest. */
int elpis_grid81_digit_array_digest(
    const uint32_t digits[GRID81_CELL_COUNT], hacf_digest *out) {
    if (!digits || !out) return SEMANTIC_E_INVAL;
    return elpis_grid81_digest_bytes(
        "elpis.semantic.grid81.digit_array.v1",
        (const uint8_t *)digits,
        GRID81_CELL_COUNT * sizeof(uint32_t),
        out);
}

/* Compute digit-class tensor digest. */
int elpis_grid81_digit_class_tensor_digest(
    const uint32_t classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT], hacf_digest *out) {
    if (!classes || !out) return SEMANTIC_E_INVAL;
    return elpis_grid81_digest_bytes(
        "elpis.semantic.grid81.digit_classes.v1",
        (const uint8_t *)classes,
        GRID81_CELL_COUNT * GRID81_DIGIT_CLASS_COUNT * sizeof(uint32_t),
        out);
}

/* Compute occupied mask digest. */
int elpis_grid81_occupied_mask_digest(
    const uint32_t mask[GRID81_CELL_COUNT], hacf_digest *out) {
    if (!mask || !out) return SEMANTIC_E_INVAL;
    return elpis_grid81_digest_bytes(
        "elpis.semantic.grid81.occupied_mask.v1",
        (const uint8_t *)mask,
        GRID81_CELL_COUNT * sizeof(uint32_t),
        out);
}

/* Compute writable mask digest. */
int elpis_grid81_writable_mask_digest(
    const uint32_t mask[GRID81_CELL_COUNT], hacf_digest *out) {
    if (!mask || !out) return SEMANTIC_E_INVAL;
    return elpis_grid81_digest_bytes(
        "elpis.semantic.grid81.writable_mask.v1",
        (const uint8_t *)mask,
        GRID81_CELL_COUNT * sizeof(uint32_t),
        out);
}

/* Zero a digest. */
void elpis_grid81_zero_digest(hacf_digest *d) {
    if (!d) return;
    memset(d->bytes, 0, HACF_DIGEST_BYTES);
}

/* Check if a digest is all-zero. Returns 1 if zero, 0 if not. */
int elpis_grid81_digest_is_zero(const hacf_digest *d) {
    if (!d) return 1;
    for (size_t i = 0; i < HACF_DIGEST_BYTES; i++) {
        if (d->bytes[i] != 0) return 0;
    }
    return 1;
}

/* Build digit-class tensor from digit array. */
void elpis_grid81_build_digit_class_tensor(
    const uint32_t digits[GRID81_CELL_COUNT],
    uint32_t classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT]) {
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        for (uint32_t j = 0; j < GRID81_DIGIT_CLASS_COUNT; j++) {
            classes[i][j] = (digits[i] == j) ? 1u : 0u;
        }
    }
}

/* Build occupied mask from digit array. */
void elpis_grid81_build_occupied_mask(
    const uint32_t digits[GRID81_CELL_COUNT],
    uint32_t mask[GRID81_CELL_COUNT]) {
    for (uint32_t i = 0; i < GRID81_CELL_COUNT; i++) {
        mask[i] = (digits[i] > 0) ? 1u : 0u;
    }
}

/* Build compiler-writable mask (all zero for P7). */
void elpis_grid81_build_writable_mask(uint32_t mask[GRID81_CELL_COUNT]) {
    memset(mask, 0, GRID81_CELL_COUNT * sizeof(uint32_t));
}
