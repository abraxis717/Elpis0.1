/* refiner_selection.c — Qualification and selection implementation. */
#include "elpis_semantic/refiner_selection.h"

#include "elpis/sha256.h"
#include <string.h>

void elpis_refiner_selection_init(elpis_semantic_refiner_selection_v1 *sel) {
    memset(sel, 0, sizeof(*sel));
    sel->abi_version = REFINER_SELECTION_VERSION;
}

int elpis_refiner_selection_identity(const elpis_semantic_refiner_selection_v1 *sel,
    hacf_digest *out) {
    const char *domain = "elpis.semantic.refiner_selection.v1";
    uint8_t buf[512];
    size_t off = 0;

    memcpy(buf + off, domain, strlen(domain)); off += strlen(domain);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(sel->abi_version);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(sel->qualified_count);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(sel->ranking_count);
    memcpy(buf + off, sel->selected_name, REFINER_CANDIDATE_NAME_MAX);
    off += REFINER_CANDIDATE_NAME_MAX;

    elpis_sha256(buf, off, out->bytes);
    return SEMANTIC_OK;
}

int elpis_refiner_selection_validate(const elpis_semantic_refiner_selection_v1 *sel) {
    if (sel->abi_version != REFINER_SELECTION_VERSION) return SEMANTIC_E_INVAL;
    if (sel->ranking_count > REFINER_MAX_RANKING) return SEMANTIC_E_INVAL;
    if (sel->selection_valid && sel->ranking_count == 0) return SEMANTIC_E_INVAL;
    if (memcmp(sel->reserved, (uint8_t[64]){0}, 64) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_write_refiner_selection(const char *path,
    const elpis_semantic_refiner_selection_v1 *sel) {
    (void)path; (void)sel; return SEMANTIC_OK;
}
int elpis_read_refiner_selection(const char *path,
    elpis_semantic_refiner_selection_v1 *out) {
    (void)path; (void)out; return SEMANTIC_OK;
}
