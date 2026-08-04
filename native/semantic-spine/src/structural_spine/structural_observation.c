/* structural_observation.c — Structural observation v1. */
#include "elpis_semantic/structural_observation.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_spine_observation_init(elpis_semantic_structural_observation_v1 *obs) {
    if (!obs) return;
    memset(obs, 0, sizeof(*obs));
    obs->abi_version = SPINE_OBSERVATION_ABI_VERSION;
}

int elpis_spine_observation_identity(
    const elpis_semantic_structural_observation_v1 *obs, hacf_digest *out) {
    if (!obs || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.structural_observation.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f;
    f = obs->abi_version;                   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, obs->topology_vertex_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, obs->source_semantic_object_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, obs->P7_capsule_digest.bytes, HACF_DIGEST_BYTES);
    f = obs->P7_primary_cell_index;         elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = obs->initial_grid81_digit;          elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = obs->final_grid81_digit;            elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = obs->initial_occupied_status;       elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = obs->final_filled_status;           elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = obs->structural_transition_class;   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = obs->observation_flags;             elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_spine_observation_validate(const elpis_semantic_structural_observation_v1 *obs) {
    if (!obs) return SEMANTIC_E_INVAL;
    if (obs->abi_version != SPINE_OBSERVATION_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (obs->P7_primary_cell_index >= 81) return SEMANTIC_E_INVAL;
    if (obs->initial_grid81_digit > 9) return SEMANTIC_E_INVAL;
    if (obs->final_grid81_digit > 9) return SEMANTIC_E_INVAL;
    if (obs->observation_flags & ~SPINE_OBS_FLAG_MASK) return SEMANTIC_E_RESERVATION;
    for (size_t i = 0; i < sizeof(obs->reserved); i++) {
        if (obs->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    return SEMANTIC_OK;
}

int elpis_spine_observation_is_readonly(const elpis_semantic_structural_observation_v1 *obs) {
    if (!obs) return 0;
    /* Structural observation is inherently read-only — it does not modify
       any semantic node, hyperedge, incidence, relation, authority, provenance,
       conflict, constellation, or topology address. */
    return 1;
}
