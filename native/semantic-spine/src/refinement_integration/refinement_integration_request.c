/* refinement_integration_request.c — Integration request v1. */
#include "elpis_semantic/refinement_integration_request.h"
#include "elpis/sha256.h"
#include "elpis_semantic/identity.h"
#include <string.h>
#include <stdio.h>

void elpis_refinement_integration_request_init(
    elpis_semantic_refinement_integration_request_v1 *r) {
    memset(r, 0, sizeof(*r));
    r->abi_version = REFINEMENT_INTEGRATION_REQUEST_VERSION;
}

int elpis_refinement_integration_request_identity(
    const elpis_semantic_refinement_integration_request_v1 *r, hacf_digest *out) {
    const char *domain = "elpis.semantic.refinement_integration_request.v1";
    size_t domain_len = 51;

    uint8_t buf[2048];
    size_t off = 0;

    memcpy(buf + off, domain, domain_len); off += domain_len;
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(r->abi_version);
    memcpy(buf + off, r->P7_structural_packet_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->backend_registry_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->active_backend_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->integration_policy_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->initial_digit_array_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->initial_digit_class_tensor_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->fixed_mask_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->writable_mask_digest.bytes, 32); off += 32;

    elpis_sha256(buf, off, out->bytes);
    return SEMANTIC_OK;
}

int elpis_refinement_integration_request_validate(
    const elpis_semantic_refinement_integration_request_v1 *r) {
    if (r->abi_version != REFINEMENT_INTEGRATION_REQUEST_VERSION)
        return SEMANTIC_E_INVAL;
    if (memcmp(r->reserved, (uint8_t[64]){0}, 64) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_write_refinement_integration_request(const char *path,
    const elpis_semantic_refinement_integration_request_v1 *r) {
    FILE *f = fopen(path, "wb");
    if (!f) return SEMANTIC_E_IO;
    size_t w = fwrite(r, sizeof(*r), 1, f);
    fclose(f);
    return w == 1 ? SEMANTIC_OK : SEMANTIC_E_IO;
}

int elpis_read_refinement_integration_request(const char *path,
    elpis_semantic_refinement_integration_request_v1 *out) {
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;
    size_t rd = fread(out, sizeof(*out), 1, f);
    fclose(f);
    return rd == 1 ? SEMANTIC_OK : SEMANTIC_E_IO;
}
