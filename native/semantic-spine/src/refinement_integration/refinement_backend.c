/* refinement_backend.c — Canonical refinement backend ABI v1. */
#include "elpis_semantic/refinement_backend.h"
#include "elpis/sha256.h"
#include "elpis_semantic/identity.h"
#include <string.h>
#include <stdio.h>

void elpis_refinement_backend_init(elpis_semantic_refinement_backend_v1 *b) {
    memset(b, 0, sizeof(*b));
    b->abi_version = REFINEMENT_BACKEND_VERSION;
}

int elpis_refinement_backend_identity(
    const elpis_semantic_refinement_backend_v1 *b, hacf_digest *out) {
    const char *domain = "elpis.semantic.refinement_backend.v1";
    size_t domain_len = 40;

    uint8_t buf[1024];
    size_t off = 0;

    memcpy(buf + off, domain, domain_len); off += domain_len;
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(b->abi_version);
    memcpy(buf + off, b->backend_name, REFINEMENT_BACKEND_NAME_MAX);
    off += REFINEMENT_BACKEND_NAME_MAX;
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(b->candidate_class);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(b->status);
    memcpy(buf + off, b->adapter_name, REFINER_ADAPTER_NAME_MAX);
    off += REFINER_ADAPTER_NAME_MAX;
    memcpy(buf + off, b->candidate_manifest.candidate_name, REFINER_CANDIDATE_NAME_MAX);
    off += REFINER_CANDIDATE_NAME_MAX;
    memcpy(buf + off, b->candidate_manifest.candidate_manifest_digest.bytes, 32);
    off += 32;

    elpis_sha256(buf, off, out->bytes);
    return SEMANTIC_OK;
}

int elpis_refinement_backend_validate(
    const elpis_semantic_refinement_backend_v1 *b) {
    if (b->abi_version != REFINEMENT_BACKEND_VERSION) return SEMANTIC_E_INVAL;
    if (b->status > REFINEMENT_STATUS_DISABLED) return SEMANTIC_E_INVAL;
    if (b->candidate_class > REFINER_CLASS_HYBRID_STRUCTURAL) return SEMANTIC_E_INVAL;
    if (b->semantic_sidecar_access != 0) return SEMANTIC_E_INVAL;
    if (b->reference_solution_access != 0) return SEMANTIC_E_INVAL;
    if (b->training_required != 0) return SEMANTIC_E_INVAL;
    if (memcmp(b->reserved, (uint8_t[64]){0}, 64) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_write_refinement_backend(const char *path,
    const elpis_semantic_refinement_backend_v1 *b) {
    FILE *f = fopen(path, "wb");
    if (!f) return SEMANTIC_E_IO;
    size_t w = fwrite(b, sizeof(*b), 1, f);
    fclose(f);
    return w == 1 ? SEMANTIC_OK : SEMANTIC_E_IO;
}

int elpis_read_refinement_backend(const char *path,
    elpis_semantic_refinement_backend_v1 *out) {
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;
    size_t r = fread(out, sizeof(*out), 1, f);
    fclose(f);
    return r == 1 ? SEMANTIC_OK : SEMANTIC_E_IO;
}
