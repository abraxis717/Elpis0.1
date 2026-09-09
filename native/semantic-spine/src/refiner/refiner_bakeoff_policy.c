/* refiner_bakeoff_policy.c — Bakeoff policy implementation. */
#include "elpis_semantic/refiner_bakeoff_policy.h"
#include "elpis/sha256.h"
#include <string.h>

void elpis_refiner_bakeoff_policy_init(elpis_semantic_refiner_bakeoff_policy_v1 *p) {
    memset(p, 0, sizeof(*p));
    p->abi_version = REFINER_BAKEOFF_POLICY_VERSION;
    p->timeout_seconds = REFINER_DEFAULT_TIMEOUT_SECONDS;
    p->bounded_policy.maximum_steps = 16;
}

int elpis_refiner_bakeoff_policy_identity(const elpis_semantic_refiner_bakeoff_policy_v1 *p,
    hacf_digest *out) {
    static const char domain[] = "elpis.semantic.refiner_bakeoff_policy.v2";
    const size_t domain_len = sizeof(domain) - 1u;
    uint8_t buf[384];
    size_t off = 0;

    memcpy(buf + off, domain, domain_len); off += domain_len;
    { uint32_t encoded_u32 = __builtin_bswap32(p->abi_version); memcpy(buf + off, &encoded_u32, 4); off += 4; }
    memcpy(buf + off, p->P10_corpus_digest.bytes, 32); off += 32;
    memcpy(buf + off, p->P10_efficacy_policy_digest.bytes, 32); off += 32;
    { uint32_t encoded_u32 = __builtin_bswap32(p->enabled_candidate_count); memcpy(buf + off, &encoded_u32, 4); off += 4; }
    for (uint32_t i = 0; i < p->enabled_candidate_count; i++) {
        memcpy(buf + off, p->enabled_candidate_digests[i].bytes, 32); off += 32;
    }
    memcpy(buf + off, &p->bounded_policy, sizeof(p->bounded_policy));
    off += sizeof(p->bounded_policy);

    elpis_sha256(buf, off, out->bytes);
    return SEMANTIC_OK;
}

int elpis_refiner_bakeoff_policy_validate(const elpis_semantic_refiner_bakeoff_policy_v1 *p) {
    if (p->abi_version != REFINER_BAKEOFF_POLICY_VERSION) return SEMANTIC_E_INVAL;
    if (p->enabled_candidate_count > REFINER_MAX_CANDIDATES) return SEMANTIC_E_INVAL;
    if (p->bounded_policy.maximum_steps == 0) return SEMANTIC_E_INVAL;
    if (p->minimum_positive_fixtures > 16) return SEMANTIC_E_INVAL;
    if (memcmp(p->reserved, (uint8_t[64]){0}, 64) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_write_refiner_bakeoff_policy(const char *path,
    const elpis_semantic_refiner_bakeoff_policy_v1 *p) {
    (void)path; (void)p; return SEMANTIC_OK;
}
int elpis_read_refiner_bakeoff_policy(const char *path,
    elpis_semantic_refiner_bakeoff_policy_v1 *out) {
    (void)path; (void)out; return SEMANTIC_OK;
}
