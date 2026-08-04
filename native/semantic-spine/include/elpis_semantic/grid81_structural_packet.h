/* elpis_semantic/grid81_structural_packet.h — Grid81 structural packet v1.
 *
 * Complete immutable structural artifact: digits, masks, digit-class tensor,
 * capsule manifest, constraint projections, trace sidecar, and P6 binding.
 *
 * Identity domain: "elpis.semantic.grid81.structural_packet.v1"
 */
#ifndef ELPIS_SEMANTIC_GRID81_STRUCTURAL_PACKET_H
#define ELPIS_SEMANTIC_GRID81_STRUCTURAL_PACKET_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/grid81_codebook.h"
#include "elpis_semantic/grid81_capsule.h"
#include "elpis_semantic/grid81_cell.h"
#include "elpis_semantic/grid81_constraint_projection.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GRID81_STRUCTURAL_PACKET_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Structural packet                                                    */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_grid81_structural_packet_v1 {
    uint32_t                          abi_version;

    /* P6 binding */
    hacf_digest                       P6_topology_handoff_digest;
    hacf_digest                       P6_topology_IR_digest;
    hacf_digest                       P6_compile_receipt_digest;

    /* Policy and template binding */
    hacf_digest                       grid81_policy_digest;
    hacf_digest                       grid81_codebook_digest;
    hacf_digest                       sudoku_template_digest;

    /* Grid81 data */
    uint32_t                          grid81_digits[GRID81_CELL_COUNT];
    uint32_t                          occupied_mask81[GRID81_CELL_COUNT];
    uint32_t                          compiler_writable_mask81[GRID81_CELL_COUNT];
    uint32_t                          grid81_digit_classes[GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT];

    /* Digests of collections */
    hacf_digest                       ordered_cell_digests[GRID81_CELL_COUNT];
    hacf_digest                       ordered_capsule_digests[GRID81_MAX_CAPSULES];
    uint32_t                          ordered_capsule_count;

    hacf_digest                       ordered_constraint_projection_digests[GRID81_MAX_CONSTRAINT_PROJECTIONS];
    uint32_t                          ordered_constraint_projection_count;

    /* Sidecar digests */
    hacf_digest                       capsule_manifest_digest;
    hacf_digest                       trace_sidecar_digest;

    /* Tensor digests */
    hacf_digest                       digit_array_digest;
    hacf_digest                       digit_class_tensor_digest;
    hacf_digest                       occupied_mask_digest;
    hacf_digest                       writable_mask_digest;

    /* Packet identity */
    hacf_digest                       structural_packet_digest;
    hacf_digest                       HACF_package_digest;

    uint8_t                           reserved[64];
} elpis_semantic_grid81_structural_packet_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize structural packet. Sets abi_version, zeroes reserved. */
void elpis_grid81_structural_packet_init(
    elpis_semantic_grid81_structural_packet_v1 *packet);

/* Compute packet identity. Domain: "elpis.semantic.grid81.structural_packet.v1" */
int elpis_grid81_structural_packet_identity(
    const elpis_semantic_grid81_structural_packet_v1 *packet, hacf_digest *out);

/* Validate all invariants: 81 cells, 810 classes, digits 0-9, masks, Sudoku,
 * capsule counts, traceability. */
int elpis_grid81_structural_packet_validate(
    const elpis_semantic_grid81_structural_packet_v1 *packet);

/* Persistence */
int elpis_write_grid81_structural_packet(const char *path,
    const elpis_semantic_grid81_structural_packet_v1 *packet);
int elpis_read_grid81_structural_packet(const char *path,
    elpis_semantic_grid81_structural_packet_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
