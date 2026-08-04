/* refinement_integration_handoff.c — Integration handoff v1. */
#include "elpis_semantic/refinement_integration_handoff.h"
#include "elpis/sha256.h"
#include "elpis_semantic/identity.h"
#include <string.h>
#include <stdio.h>

void elpis_refinement_integration_handoff_init(
    elpis_semantic_refinement_integration_handoff_v1 *h) {
    memset(h, 0, sizeof(*h));
    h->abi_version = REFINEMENT_INTEGRATION_HANDOFF_VERSION;
}

int elpis_refinement_integration_handoff_identity(
    const elpis_semantic_refinement_integration_handoff_v1 *h, hacf_digest *out) {
    const char *domain = "elpis.semantic.refinement_integration_handoff.v1";
    size_t domain_len = 48;

    uint8_t buf[1024];
    size_t off = 0;

    memcpy(buf + off, domain, domain_len); off += domain_len;
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(h->abi_version);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(h->handoff_kind);
    memcpy(buf + off, h->P11_replacement_handoff_digest.bytes, 32); off += 32;
    memcpy(buf + off, h->backend_registry_digest.bytes, 32); off += 32;
    memcpy(buf + off, h->selected_candidate_digest.bytes, 32); off += 32;
    memcpy(buf + off, h->selected_adapter_digest.bytes, 32); off += 32;
    memcpy(buf + off, h->integration_policy_digest.bytes, 32); off += 32;
    memcpy(buf + off, h->production_execution_digest.bytes, 32); off += 32;
    memcpy(buf + off, h->corpus_regression_digest.bytes, 32); off += 32;

    elpis_sha256(buf, off, out->bytes);
    return SEMANTIC_OK;
}

int elpis_refinement_integration_handoff_validate(
    const elpis_semantic_refinement_integration_handoff_v1 *h) {
    if (h->abi_version != REFINEMENT_INTEGRATION_HANDOFF_VERSION)
        return SEMANTIC_E_INVAL;
    if (h->handoff_kind > HANDOFF_CANONICAL_STRUCTURAL_REFINER_INTEGRATED)
        return SEMANTIC_E_INVAL;
    if (h->runtime_admission != 0) return SEMANTIC_E_INVAL;
    if (h->no_projector_target != 1) return SEMANTIC_E_INVAL;
    if (h->no_residual81 != 1) return SEMANTIC_E_INVAL;
    if (h->no_training != 1) return SEMANTIC_E_INVAL;
    if (h->no_gpu_dependency != 1) return SEMANTIC_E_INVAL;
    if (memcmp(h->reserved, (uint8_t[128]){0}, 128) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_write_refinement_integration_handoff(const char *path,
    const elpis_semantic_refinement_integration_handoff_v1 *h) {
    FILE *f = fopen(path, "wb");
    if (!f) return SEMANTIC_E_IO;
    size_t w = fwrite(h, sizeof(*h), 1, f);
    fclose(f);
    return w == 1 ? SEMANTIC_OK : SEMANTIC_E_IO;
}

int elpis_read_refinement_integration_handoff(const char *path,
    elpis_semantic_refinement_integration_handoff_v1 *out) {
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;
    size_t rd = fread(out, sizeof(*out), 1, f);
    fclose(f);
    return rd == 1 ? SEMANTIC_OK : SEMANTIC_E_IO;
}
