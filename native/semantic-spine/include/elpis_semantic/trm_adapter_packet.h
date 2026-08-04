/* elpis_semantic/trm_adapter_packet.h — Immutable TRM adapter packet v1.
 *
 * Complete sealed artifact binding P7 structural packet, TRM ABI,
 * adapter policy, input tensor, and mutability masks. Consumed by
 * the frozen TRM execution layer (P9).
 *
 * Identity domain: "elpis.semantic.trm_adapter_packet.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_ADAPTER_PACKET_H
#define ELPIS_SEMANTIC_TRM_ADAPTER_PACKET_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_ADAPTER_PACKET_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Adapter packet                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_trm_adapter_packet_v1 {
    uint32_t                          abi_version;

    /* P7 binding */
    hacf_digest                       P7_handoff_digest;
    hacf_digest                       P7_structural_packet_digest;
    hacf_digest                       P7_compile_receipt_digest;

    /* TRM binding */
    hacf_digest                       TRM_abi_digest;
    hacf_digest                       adapter_policy_digest;

    /* Tensor and mask binding */
    hacf_digest                       input_tensor_digest;
    hacf_digest                       fixed_mask_digest;
    hacf_digest                       writable_mask_digest;
    hacf_digest                       mutability_receipt_digest;

    /* Source data digests */
    hacf_digest                       input_digit_array_digest;
    hacf_digest                       input_digit_class_tensor_digest;
    hacf_digest                       input_sudoku_template_digest;

    /* Trace */
    hacf_digest                       adapter_trace_digest;

    /* HACF */
    hacf_digest                       HACF_package_digest;

    /* Packet identity */
    hacf_digest                       adapter_packet_digest;

    uint8_t                           reserved[64];
} elpis_semantic_trm_adapter_packet_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                             */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize: set ABI version, zero reserved. */
void elpis_trm_adapter_packet_init(
    elpis_semantic_trm_adapter_packet_v1 *packet);

/* Compute packet identity. Domain: "elpis.semantic.trm_adapter_packet.v1" */
int elpis_trm_adapter_packet_identity(
    const elpis_semantic_trm_adapter_packet_v1 *packet, hacf_digest *out);

/* Validate: P7 verified, TRM ABI verified, tensor verified, masks verified,
 * semantic sidecar absent from tensor, HACF valid. */
int elpis_trm_adapter_packet_validate(
    const elpis_semantic_trm_adapter_packet_v1 *packet);

/* Persistence */
int elpis_write_trm_adapter_packet(const char *path,
    const elpis_semantic_trm_adapter_packet_v1 *packet);
int elpis_read_trm_adapter_packet(const char *path,
    elpis_semantic_trm_adapter_packet_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
