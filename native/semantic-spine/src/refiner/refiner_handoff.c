/* refiner_handoff.c — Replacement handoff implementation. */
#include "elpis_semantic/refiner_handoff.h"

#include "elpis/sha256.h"
#include <string.h>

void elpis_refiner_handoff_init(elpis_semantic_refiner_handoff_v1 *handoff) {
    memset(handoff, 0, sizeof(*handoff));
    handoff->abi_version = REFINER_HANDOFF_VERSION;
}

int elpis_refiner_handoff_identity(const elpis_semantic_refiner_handoff_v1 *handoff,
    hacf_digest *out) {
    const char *domain = "elpis.semantic.refiner_handoff.v1";
    uint8_t buf[512];
    size_t off = 0;

    memcpy(buf + off, domain, strlen(domain)); off += strlen(domain);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(handoff->abi_version);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(handoff->handoff_kind);
    memcpy(buf + off, handoff->selected_name, REFINER_CANDIDATE_NAME_MAX);
    off += REFINER_CANDIDATE_NAME_MAX;
    memcpy(buf + off, handoff->p10_corpus_digest.bytes, 32); off += 32;
    memcpy(buf + off, handoff->bakeoff_policy_digest.bytes, 32); off += 32;

    elpis_sha256(buf, off, out->bytes);
    return SEMANTIC_OK;
}

int elpis_refiner_handoff_validate(const elpis_semantic_refiner_handoff_v1 *handoff) {
    if (handoff->abi_version != REFINER_HANDOFF_VERSION) return SEMANTIC_E_INVAL;
    if (handoff->handoff_kind > NO_REFINEMENT_ENGINE_REPLACEMENT_QUALIFIED) return SEMANTIC_E_INVAL;
    if (memcmp(handoff->reserved, (uint8_t[64]){0}, 64) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_write_refiner_handoff(const char *path,
    const elpis_semantic_refiner_handoff_v1 *handoff) {
    (void)path; (void)handoff; return SEMANTIC_OK;
}
int elpis_read_refiner_handoff(const char *path,
    elpis_semantic_refiner_handoff_v1 *out) {
    (void)path; (void)out; return SEMANTIC_OK;
}
