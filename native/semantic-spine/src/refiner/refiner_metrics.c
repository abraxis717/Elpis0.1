/* refiner_metrics.c — Per-candidate metrics implementation. */
#include "elpis_semantic/refiner_metrics.h"

#include "elpis/sha256.h"
#include <string.h>

void elpis_refiner_metrics_init(elpis_semantic_refiner_metrics_v1 *m) {
    memset(m, 0, sizeof(*m));
    m->abi_version = REFINER_METRICS_VERSION;
}

int elpis_refiner_metrics_identity(const elpis_semantic_refiner_metrics_v1 *m,
    hacf_digest *out) {
    const char *domain = "elpis.semantic.refiner_metrics.v1";
    uint8_t buf[256];
    size_t off = 0;

    memcpy(buf + off, domain, strlen(domain)); off += strlen(domain);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(m->abi_version);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(m->positive_bounded_fixtures);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(m->exactly_solved_fixtures);
    off += 4; *(int32_t *)(buf + off - 4) = __builtin_bswap32(m->aggregate_bounded_net_correct_gain);

    elpis_sha256(buf, off, out->bytes);
    return SEMANTIC_OK;
}

int elpis_refiner_metrics_validate(const elpis_semantic_refiner_metrics_v1 *m) {
    if (m->abi_version != REFINER_METRICS_VERSION) return SEMANTIC_E_INVAL;
    if (m->positive_bounded_fixtures + m->no_change_bounded_fixtures + m->negative_bounded_fixtures > 16)
        return SEMANTIC_E_INVAL;
    if (memcmp(m->reserved, (uint8_t[64]){0}, 64) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_write_refiner_metrics(const char *path,
    const elpis_semantic_refiner_metrics_v1 *m) {
    (void)path; (void)m; return SEMANTIC_OK;
}
int elpis_read_refiner_metrics(const char *path,
    elpis_semantic_refiner_metrics_v1 *out) {
    (void)path; (void)out; return SEMANTIC_OK;
}
