/* refinement_backend_registry.c — Backend registry v1. */
#include "elpis_semantic/refinement_backend_registry.h"
#include "elpis/sha256.h"
#include "elpis_semantic/identity.h"
#include <string.h>
#include <stdio.h>

void elpis_refinement_backend_registry_init(
    elpis_semantic_refinement_backend_registry_v1 *r) {
    memset(r, 0, sizeof(*r));
    r->abi_version = REFINEMENT_BACKEND_REGISTRY_VERSION;
}

int elpis_refinement_backend_registry_add(
    elpis_semantic_refinement_backend_registry_v1 *r,
    const elpis_semantic_refinement_backend_v1 *backend) {
    if (r->backend_count >= REFINEMENT_MAX_BACKENDS) return SEMANTIC_E_INVAL;
    if (elpis_refinement_backend_validate(backend) != SEMANTIC_OK)
        return SEMANTIC_E_INVAL;

    for (uint32_t i = 0; i < r->backend_count; i++) {
        if (strcmp(r->backends[i].backend_name, backend->backend_name) == 0)
            return SEMANTIC_E_DUPLICATE;
    }

    memcpy(&r->backends[r->backend_count], backend, sizeof(*backend));
    r->backend_count++;

    /* Update active canonical digest */
    uint32_t active_count = 0;
    for (uint32_t i = 0; i < r->backend_count; i++) {
        if (r->backends[i].status == REFINEMENT_STATUS_ACTIVE_CANONICAL) {
            active_count++;
            memcpy(r->active_canonical_digest.bytes,
                   r->backends[i].backend_digest.bytes, 32);
        }
    }
    if (active_count != 1) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

const elpis_semantic_refinement_backend_v1 *
elpis_refinement_backend_registry_resolve_canonical(
    const elpis_semantic_refinement_backend_registry_v1 *r) {
    for (uint32_t i = 0; i < r->backend_count; i++) {
        if (r->backends[i].status == REFINEMENT_STATUS_ACTIVE_CANONICAL)
            return &r->backends[i];
    }
    return NULL;
}

const elpis_semantic_refinement_backend_v1 *
elpis_refinement_backend_registry_resolve_by_name(
    const elpis_semantic_refinement_backend_registry_v1 *r,
    const char *name) {
    for (uint32_t i = 0; i < r->backend_count; i++) {
        if (strcmp(r->backends[i].backend_name, name) == 0)
            return &r->backends[i];
    }
    return NULL;
}

int elpis_refinement_backend_registry_validate(
    const elpis_semantic_refinement_backend_registry_v1 *r) {
    if (r->abi_version != REFINEMENT_BACKEND_REGISTRY_VERSION)
        return SEMANTIC_E_INVAL;
    if (r->backend_count == 0) return SEMANTIC_E_INVAL;
    if (r->backend_count > REFINEMENT_MAX_BACKENDS) return SEMANTIC_E_INVAL;

    uint32_t active_count = 0;
    for (uint32_t i = 0; i < r->backend_count; i++) {
        if (elpis_refinement_backend_validate(&r->backends[i]) != SEMANTIC_OK)
            return SEMANTIC_E_INVAL;
        if (r->backends[i].status == REFINEMENT_STATUS_ACTIVE_CANONICAL) {
            active_count++;
        }
    }
    if (active_count != 1) return SEMANTIC_E_INVAL;
    if (memcmp(r->reserved, (uint8_t[64]){0}, 64) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_refinement_backend_registry_identity(
    const elpis_semantic_refinement_backend_registry_v1 *r, hacf_digest *out) {
    const char *domain = "elpis.semantic.refinement_backend_registry.v1";
    size_t domain_len = 48;

    uint8_t buf[2048];
    size_t off = 0;

    memcpy(buf + off, domain, domain_len); off += domain_len;
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(r->abi_version);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(r->backend_count);
    for (uint32_t i = 0; i < r->backend_count; i++) {
        memcpy(buf + off, r->backends[i].backend_name, REFINEMENT_BACKEND_NAME_MAX);
        off += REFINEMENT_BACKEND_NAME_MAX;
        memcpy(buf + off, r->backends[i].backend_digest.bytes, 32);
        off += 32;
    }
    memcpy(buf + off, r->active_canonical_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->P11_final_report_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->P11_selection_result_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->P11_replacement_handoff_digest.bytes, 32); off += 32;

    elpis_sha256(buf, off, out->bytes);
    return SEMANTIC_OK;
}

int elpis_write_refinement_backend_registry(const char *path,
    const elpis_semantic_refinement_backend_registry_v1 *r) {
    FILE *f = fopen(path, "wb");
    if (!f) return SEMANTIC_E_IO;
    size_t w = fwrite(r, sizeof(*r), 1, f);
    fclose(f);
    return w == 1 ? SEMANTIC_OK : SEMANTIC_E_IO;
}

int elpis_read_refinement_backend_registry(const char *path,
    elpis_semantic_refinement_backend_registry_v1 *out) {
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;
    size_t rd = fread(out, sizeof(*out), 1, f);
    fclose(f);
    return rd == 1 ? SEMANTIC_OK : SEMANTIC_E_IO;
}
