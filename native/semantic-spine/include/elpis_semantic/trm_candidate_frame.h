/* elpis_semantic/trm_candidate_frame.h — TRM candidate-output frame ABI v1.
 *
 * The only candidate format accepted by the P8 output guard.
 * Represents the raw output of frozen TRM execution before decoding.
 *
 * Identity domain: "elpis.semantic.trm_candidate_frame.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_CANDIDATE_FRAME_H
#define ELPIS_SEMANTIC_TRM_CANDIDATE_FRAME_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/trm_abi.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_CANDIDATE_FRAME_VERSION 1u

/* Candidate payload element count for [1,81,10] frames */
#define TRM_CANDIDATE_ELEMENTS  (1u * GRID81_CELL_COUNT * GRID81_DIGIT_CLASS_COUNT)

/* ──────────────────────────────────────────────────────────────────── */
/* Candidate frame flags                                                  */
/* ──────────────────────────────────────────────────────────────────── */

#define TRM_CANDIDATE_FLAG_NONE         0u
#define TRM_CANDIDATE_FLAG_SCORES       0x01u
#define TRM_CANDIDATE_FLAG_PROBABILITIES 0x02u
#define TRM_CANDIDATE_FLAG_ONE_HOT      0x04u
#define TRM_CANDIDATE_FLAG_INDICES      0x08u
#define TRM_CANDIDATE_FLAG_MASK         0x0Fu

/* ──────────────────────────────────────────────────────────────────── */
/* Candidate frame                                                          */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_trm_candidate_frame_v1 {
    uint32_t                          abi_version;

    /* Source binding */
    hacf_digest                       source_adapter_packet_digest;
    hacf_digest                       TRM_abi_digest;

    /* Candidate kind */
    uint32_t                          candidate_kind; /* trm_output_semantics */

    /* Shape and layout */
    uint32_t                          rank;
    uint32_t                          dimensions[4];
    uint32_t                          dtype;    /* 0=FLOAT32 */
    uint32_t                          byte_order; /* 0=LITTLE_ENDIAN */
    uint32_t                          layout;   /* 0=ROW_MAJOR_CONTIGUOUS */

    /* Size */
    uint32_t                          element_count;
    uint32_t                          payload_byte_count;

    /* Payload: candidate values (scores, probs, one-hot, or indices) */
    float                             candidate[TRM_CANDIDATE_ELEMENTS];

    /* Flags and digests */
    uint32_t                          candidate_frame_flags;
    hacf_digest                       candidate_payload_digest;
    hacf_digest                       candidate_frame_digest;

    uint8_t                           reserved[64];
} elpis_semantic_trm_candidate_frame_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                             */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize: set ABI version, zero payload and reserved. */
void elpis_trm_candidate_frame_init(
    elpis_semantic_trm_candidate_frame_v1 *frame);

/* Compute frame identity. Domain: "elpis.semantic.trm_candidate_frame.v1" */
int elpis_trm_candidate_frame_identity(
    const elpis_semantic_trm_candidate_frame_v1 *frame, hacf_digest *out);

/* Validate: source adapter, ABI digest, rank, dimensions, dtype, candidate_kind,
 * no NaN/Inf, valid one-hot values if applicable, class indices in range. */
int elpis_trm_candidate_frame_validate(
    const elpis_semantic_trm_candidate_frame_v1 *frame);

/* Persistence */
int elpis_write_trm_candidate_frame(const char *path,
    const elpis_semantic_trm_candidate_frame_v1 *frame);
int elpis_read_trm_candidate_frame(const char *path,
    elpis_semantic_trm_candidate_frame_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
