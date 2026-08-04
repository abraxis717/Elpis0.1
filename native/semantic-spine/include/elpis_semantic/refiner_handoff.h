/* elpis_semantic/refiner_handoff.h — Replacement handoff v1.
 *
 * Identity domain: "elpis.semantic.refiner_handoff.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINER_HANDOFF_H
#define ELPIS_SEMANTIC_REFINER_HANDOFF_H

#include "elpis_semantic/refiner_candidate.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINER_HANDOFF_VERSION 1u

typedef enum refiner_handoff_kind {
    REFINEMENT_ENGINE_REPLACEMENT_CANDIDATE = 0u,
    NO_REFINEMENT_ENGINE_REPLACEMENT_QUALIFIED = 1u,
} refiner_handoff_kind;

typedef struct elpis_semantic_refiner_handoff_v1 {
    uint32_t                              abi_version;
    uint32_t                              handoff_kind;  /* refiner_handoff_kind */

    /* Selected candidate */
    char                                  selected_name[REFINER_CANDIDATE_NAME_MAX];
    hacf_digest                           selected_manifest_digest;

    /* Bindings */
    hacf_digest                           p8_frame_schema_digest;
    hacf_digest                           p8_p9_guard_digest;
    hacf_digest                           p10_corpus_digest;
    hacf_digest                           bakeoff_policy_digest;
    hacf_digest                           comparative_ranking_digest;
    hacf_digest                           selection_receipt_digest;

    /* Immutability */
    uint8_t                               artifact_immutability;
    uint8_t                               deterministic_replay;
    uint8_t                               runtime_admission;

    /* Handoff identity */
    hacf_digest                           handoff_digest;
    uint8_t                               reserved[64];
} elpis_semantic_refiner_handoff_v1;

void elpis_refiner_handoff_init(elpis_semantic_refiner_handoff_v1 *handoff);
int elpis_refiner_handoff_identity(const elpis_semantic_refiner_handoff_v1 *handoff,
    hacf_digest *out);
int elpis_refiner_handoff_validate(const elpis_semantic_refiner_handoff_v1 *handoff);

int elpis_write_refiner_handoff(const char *path,
    const elpis_semantic_refiner_handoff_v1 *handoff);
int elpis_read_refiner_handoff(const char *path,
    elpis_semantic_refiner_handoff_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
