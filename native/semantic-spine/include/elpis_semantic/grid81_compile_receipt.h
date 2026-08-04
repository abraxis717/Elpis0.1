/* elpis_semantic/grid81_compile_receipt.h — Compilation receipt v1.
 *
 * Immutable record of P7 Grid81 compilation: input/output counts,
 * verification counters, disposition, and binding digests.
 *
 * Identity domain: "elpis.semantic.grid81_compile_receipt.v1"
 */
#ifndef ELPIS_SEMANTIC_GRID81_COMPILE_RECEIPT_H
#define ELPIS_SEMANTIC_GRID81_COMPILE_RECEIPT_H

#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GRID81_COMPILE_RECEIPT_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Compile disposition                                                  */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum grid81_compile_disposition {
    GRID81_COMPILE_COMPLETE                       = 0,
    GRID81_COMPILE_BLOCKED_BY_INPUT               = 1,
    GRID81_COMPILE_BLOCKED_BY_ABI                 = 2,
    GRID81_COMPILE_BLOCKED_BY_POLICY              = 3,
    GRID81_COMPILE_BLOCKED_BY_CODEBOOK            = 4,
    GRID81_COMPILE_BLOCKED_BY_CAPACITY            = 5,
    GRID81_COMPILE_BLOCKED_BY_PLACEMENT           = 6,
    GRID81_COMPILE_BLOCKED_BY_SUDOKU_VALIDITY     = 7,
    GRID81_COMPILE_BLOCKED_BY_CONSTRAINT          = 8,
    GRID81_COMPILE_BLOCKED_BY_TRACEABILITY        = 9,
    GRID81_COMPILE_BLOCKED_BY_INVARIANT           = 10,
    GRID81_COMPILE_BLOCKED_INTERNAL               = 11,
} grid81_compile_disposition;

/* ──────────────────────────────────────────────────────────────────── */
/* Compile receipt                                                      */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_grid81_compile_receipt_v1 {
    uint32_t                          abi_version;

    /* Input binding */
    hacf_digest                       P6_handoff_digest;
    hacf_digest                       P6_topology_IR_digest;

    /* Policy binding */
    hacf_digest                       grid81_policy_digest;
    hacf_digest                       grid81_codebook_digest;
    hacf_digest                       sudoku_template_digest;

    /* Input counts */
    uint32_t                          input_topology_vertex_count;
    uint32_t                          input_topology_incidence_count;
    uint32_t                          input_constraint_count;

    /* Output counts */
    uint32_t                          capsule_count;
    uint32_t                          occupied_cell_count;
    uint32_t                          empty_cell_count;
    uint32_t                          packed_collision_count;
    uint32_t                          projected_constraint_count;

    /* Verification counters — must be zero for COMPLETE */
    uint32_t                          unmapped_vertex_count;
    uint32_t                          untraceable_incidence_count;
    uint32_t                          unprojected_constraint_count;
    uint32_t                          semantic_relation_invention_count;
    uint32_t                          semantic_relation_loss_count;
    uint32_t                          authority_change_count;

    /* Output identity */
    hacf_digest                       structural_packet_digest;
    hacf_digest                       compiler_trace_digest;

    /* Disposition and identity */
    uint32_t                          compile_disposition; /* grid81_compile_disposition */
    hacf_digest                       receipt_digest;
    hacf_digest                       HACF_package_digest;

    uint8_t                           reserved[64];
} elpis_semantic_grid81_compile_receipt_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize receipt. Sets abi_version, zeroes reserved. */
void elpis_grid81_compile_receipt_init(
    elpis_semantic_grid81_compile_receipt_v1 *receipt);

/* Compute receipt identity. Domain: "elpis.semantic.grid81_compile_receipt.v1" */
int elpis_grid81_compile_receipt_identity(
    const elpis_semantic_grid81_compile_receipt_v1 *receipt, hacf_digest *out);

/* Validate receipt: ABI, disposition, verification counters, reserved zeroed. */
int elpis_grid81_compile_receipt_validate(
    const elpis_semantic_grid81_compile_receipt_v1 *receipt);

/* Check qualification: disposition == COMPLETE and all verification counters zero. */
int elpis_grid81_compile_receipt_is_qualified(
    const elpis_semantic_grid81_compile_receipt_v1 *receipt);

/* Persistence */
int elpis_write_grid81_compile_receipt(const char *path,
    const elpis_semantic_grid81_compile_receipt_v1 *receipt);
int elpis_read_grid81_compile_receipt(const char *path,
    elpis_semantic_grid81_compile_receipt_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
