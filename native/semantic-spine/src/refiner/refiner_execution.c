/* refiner_execution.c — Execution transaction implementation. */
#include "elpis_semantic/refiner_execution.h"

#include "elpis/sha256.h"
#include <string.h>

void elpis_refiner_execution_init(elpis_semantic_refiner_execution_v1 *exec) {
    memset(exec, 0, sizeof(*exec));
    exec->abi_version = REFINER_EXECUTION_VERSION;
}

int elpis_refiner_execution_identity(const elpis_semantic_refiner_execution_v1 *exec,
    hacf_digest *out) {
    const char *domain = "elpis.semantic.refiner_execution.v1";
    uint8_t buf[256];
    size_t off = 0;

    memcpy(buf + off, domain, strlen(domain)); off += strlen(domain);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(exec->abi_version);
    memcpy(buf + off, exec->candidate_manifest_digest.bytes, 32); off += 32;
    memcpy(buf + off, exec->input_state_digest.bytes, 32); off += 32;
    memcpy(buf + off, exec->output_state_digest.bytes, 32); off += 32;
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(exec->disposition);

    elpis_sha256(buf, off, out->bytes);
    return SEMANTIC_OK;
}

int elpis_refiner_execution_validate(const elpis_semantic_refiner_execution_v1 *exec) {
    if (exec->abi_version != REFINER_EXECUTION_VERSION) return SEMANTIC_E_INVAL;
    if (exec->disposition > REFINER_EXECUTION_BLOCKED_INTERNAL) return SEMANTIC_E_INVAL;
    if (memcmp(exec->reserved, (uint8_t[64]){0}, 64) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_write_refiner_execution(const char *path,
    const elpis_semantic_refiner_execution_v1 *exec) {
    (void)path; (void)exec; return SEMANTIC_OK;
}
int elpis_read_refiner_execution(const char *path,
    elpis_semantic_refiner_execution_v1 *out) {
    (void)path; (void)out; return SEMANTIC_OK;
}
