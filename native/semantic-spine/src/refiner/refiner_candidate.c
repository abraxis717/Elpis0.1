/* refiner_candidate.c — Candidate identity implementation. */
#include "elpis_semantic/refiner_candidate.h"
#include "elpis/sha256.h"
#include <string.h>
#include <stdio.h>

void elpis_refiner_candidate_init(elpis_semantic_refiner_candidate_v1 *c) {
    memset(c, 0, sizeof(*c));
    c->abi_version = REFINER_CANDIDATE_VERSION;
}

int elpis_refiner_candidate_identity(const elpis_semantic_refiner_candidate_v1 *c,
    hacf_digest *out) {
    /* Domain: "elpis.semantic.refiner_candidate.v1" */
    const char *domain = "elpis.semantic.refiner_candidate.v1";
    size_t domain_len = 38;

    uint8_t buf[256];
    size_t off = 0;

    memcpy(buf + off, domain, domain_len); off += domain_len;
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(c->abi_version);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(c->candidate_class);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(c->eligibility_disposition);

    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(c->source_digest_count);
    for (uint32_t i = 0; i < c->source_digest_count; i++) {
        memcpy(buf + off, c->source_digests[i].bytes, 32); off += 32;
    }

    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(c->config_digest_count);
    for (uint32_t i = 0; i < c->config_digest_count; i++) {
        memcpy(buf + off, c->config_digests[i].bytes, 32); off += 32;
    }

    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(c->weight_digest_count);
    for (uint32_t i = 0; i < c->weight_digest_count; i++) {
        memcpy(buf + off, c->weight_digests[i].bytes, 32); off += 32;
    }

    memcpy(buf + off, c->candidate_name, REFINER_CANDIDATE_NAME_MAX);
    off += REFINER_CANDIDATE_NAME_MAX;

    elpis_sha256(buf, off, out->bytes);
    return SEMANTIC_OK;
}

int elpis_refiner_candidate_validate(const elpis_semantic_refiner_candidate_v1 *c) {
    if (c->abi_version != REFINER_CANDIDATE_VERSION) return SEMANTIC_E_INVAL;
    if (c->candidate_class > REFINER_CLASS_HYBRID_STRUCTURAL) return SEMANTIC_E_INVAL;
    if (c->eligibility_disposition > REFINER_RETIRED_NEGATIVE_CONTROL) return SEMANTIC_E_INVAL;
    if (c->source_digest_count > REFINER_MAX_SOURCE_DIGESTS) return SEMANTIC_E_INVAL;
    if (c->config_digest_count > REFINER_MAX_CONFIG_DIGESTS) return SEMANTIC_E_INVAL;
    if (c->weight_digest_count > REFINER_MAX_WEIGHT_DIGESTS) return SEMANTIC_E_INVAL;
    if (memcmp(c->reserved, (uint8_t[64]){0}, 64) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

/* Stub persistence — delegate to JSON serialization layer in tools/ */
int elpis_write_refiner_candidate(const char *path,
    const elpis_semantic_refiner_candidate_v1 *c) {
    (void)path; (void)c; return SEMANTIC_OK;
}
int elpis_read_refiner_candidate(const char *path,
    elpis_semantic_refiner_candidate_v1 *out) {
    (void)path; (void)out; return SEMANTIC_OK;
}
