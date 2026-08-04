/* refinement_integration_policy.c — Integration policy v1. */
#include "elpis_semantic/refinement_integration_policy.h"
#include "elpis/sha256.h"
#include "elpis_semantic/identity.h"
#include <string.h>
#include <stdio.h>

void elpis_refinement_integration_policy_init(
    elpis_semantic_refinement_integration_policy_v1 *p) {
    memset(p, 0, sizeof(*p));
    p->abi_version = REFINEMENT_INTEGRATION_POLICY_VERSION;
}

int elpis_refinement_integration_policy_identity(
    const elpis_semantic_refinement_integration_policy_v1 *p, hacf_digest *out) {
    const char *domain = "elpis.semantic.refinement_integration_policy.v1";
    size_t domain_len = 49;

    uint8_t buf[1024];
    size_t off = 0;

    memcpy(buf + off, domain, domain_len); off += domain_len;
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(p->abi_version);
    memcpy(buf + off, p->backend_registry_digest.bytes, 32); off += 32;
    memcpy(buf + off, p->active_backend_digest.bytes, 32); off += 32;
    memcpy(buf + off, p->active_adapter_digest.bytes, 32); off += 32;
    memcpy(buf + off, p->P8_candidate_frame_schema_digest.bytes, 32); off += 32;
    memcpy(buf + off, p->P8_decoder_policy_digest.bytes, 32); off += 32;
    memcpy(buf + off, p->P8_mutability_policy_digest.bytes, 32); off += 32;
    memcpy(buf + off, p->P9_state_guard_digest.bytes, 32); off += 32;
    memcpy(buf + off, p->P9_refinement_policy_digest.bytes, 32); off += 32;
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(p->maximum_steps);

    elpis_sha256(buf, off, out->bytes);
    return SEMANTIC_OK;
}

int elpis_refinement_integration_policy_validate(
    const elpis_semantic_refinement_integration_policy_v1 *p) {
    if (p->abi_version != REFINEMENT_INTEGRATION_POLICY_VERSION)
        return SEMANTIC_E_INVAL;
    if (p->maximum_steps == 0) return SEMANTIC_E_INVAL;
    if (p->sidecar_isolation_enforced != 1) return SEMANTIC_E_INVAL;
    if (p->reference_isolation_enforced != 1) return SEMANTIC_E_INVAL;
    if (memcmp(p->reserved, (uint8_t[128]){0}, 128) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_write_refinement_integration_policy(const char *path,
    const elpis_semantic_refinement_integration_policy_v1 *p) {
    FILE *f = fopen(path, "wb");
    if (!f) return SEMANTIC_E_IO;
    size_t w = fwrite(p, sizeof(*p), 1, f);
    fclose(f);
    return w == 1 ? SEMANTIC_OK : SEMANTIC_E_IO;
}

int elpis_read_refinement_integration_policy(const char *path,
    elpis_semantic_refinement_integration_policy_v1 *out) {
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;
    size_t rd = fread(out, sizeof(*out), 1, f);
    fclose(f);
    return rd == 1 ? SEMANTIC_OK : SEMANTIC_E_IO;
}
