/* elpis_semantic/structural_observation.h — Structural observation v1.
 *
 * Read-only attachment mapping topology vertices back through the P7 capsule
 * to final Grid81 structural state. Does NOT modify semantic objects.
 *
 * Identity domain: "elpis.semantic.structural_observation.v1"
 */
#ifndef ELPIS_SEMANTIC_STRUCTURAL_OBSERVATION_H
#define ELPIS_SEMANTIC_STRUCTURAL_OBSERVATION_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SPINE_OBSERVATION_ABI_VERSION 1u

typedef enum spine_structural_transition_class {
    SPINE_TRANSITION_UNCHANGED = 0,
    SPINE_TRANSITION_EMPTY_TO_FILLED = 1,
    SPINE_TRANSITION_FILLED_TO_FILLED = 2,
} spine_structural_transition_class;

typedef enum spine_observation_flags {
    SPINE_OBS_FLAG_NONE          = 0u,
    SPINE_OBS_FLAG_PRIMARY_CELL  = 0x01u,
    SPINE_OBS_FLAG_SECONDARY     = 0x02u,
    SPINE_OBS_FLAG_MASK          = 0x03u,
} spine_observation_flags;

typedef struct elpis_semantic_structural_observation_v1 {
    uint32_t                          abi_version;

    /* Source identity chain */
    hacf_digest                       topology_vertex_digest;
    hacf_digest                       source_semantic_object_digest;
    hacf_digest                       P7_capsule_digest;

    /* Structural mapping */
    uint32_t                          P7_primary_cell_index;
    uint32_t                          initial_grid81_digit;
    uint32_t                          final_grid81_digit;
    uint32_t                          initial_occupied_status;
    uint32_t                          final_filled_status;
    uint32_t                          structural_transition_class;

    /* Observation identity */
    uint32_t                          observation_flags;
    hacf_digest                       observation_digest;

    uint8_t                           reserved[64];
} elpis_semantic_structural_observation_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_spine_observation_init(
    elpis_semantic_structural_observation_v1 *obs);
int elpis_spine_observation_identity(
    const elpis_semantic_structural_observation_v1 *obs, hacf_digest *out);
int elpis_spine_observation_validate(
    const elpis_semantic_structural_observation_v1 *obs);
int elpis_spine_observation_is_readonly(
    const elpis_semantic_structural_observation_v1 *obs);

#ifdef __cplusplus
}
#endif

#endif /* ELPIS_SEMANTIC_STRUCTURAL_OBSERVATION_H */
