/* elpis_semantic/trm_mutability.h — TRM mutability record v1.
 *
 * Derives fixed/writable masks from P7 digits and occupied mask under
 * the sealed adapter policy. Every cell is exactly one of fixed or
 * writable.
 *
 * Identity domain: "elpis.semantic.trm_mutability.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_MUTABILITY_H
#define ELPIS_SEMANTIC_TRM_MUTABILITY_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_MUTABILITY_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Mutability disposition                                                 */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum trm_mutability_disposition {
    TRM_MUTABILITY_NORMAL = 0u,
    TRM_MUTABILITY_NO_MUTABLE_CELLS = 1u,
} trm_mutability_disposition;

/* ──────────────────────────────────────────────────────────────────── */
/* Mutability record                                                      */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_trm_mutability_v1 {
    uint32_t                          abi_version;

    /* Source digests */
    hacf_digest                       P7_structural_packet_digest;
    hacf_digest                       P7_digit_array_digest;
    hacf_digest                       P7_occupied_mask_digest;
    hacf_digest                       P7_compiler_writable_mask_digest;

    /* Derived masks */
    uint32_t                          fixed_mask81[GRID81_CELL_COUNT];
    uint32_t                          writable_mask81[GRID81_CELL_COUNT];

    /* Counts */
    uint32_t                          fixed_cell_count;
    uint32_t                          writable_cell_count;

    /* Disposition */
    uint32_t                          disposition; /* trm_mutability_disposition */

    /* Mask digests */
    hacf_digest                       fixed_mask_digest;
    hacf_digest                       writable_mask_digest;

    /* Receipt identity */
    hacf_digest                       mutability_policy_digest;
    hacf_digest                       mutability_receipt_digest;

    uint8_t                           reserved[64];
} elpis_semantic_trm_mutability_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                             */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize: zero reserved, set ABI version. */
void elpis_trm_mutability_init(elpis_semantic_trm_mutability_v1 *mut);

/* Derive masks from P7 digits and occupied mask.
 * fixed[i] = 1 when digit[i]!=0 || occupied[i]==1
 * writable[i] = 1 when digit[i]==0 && occupied[i]==0 */
int elpis_trm_mutability_derive(
    elpis_semantic_trm_mutability_v1 *mut,
    const uint32_t digits[GRID81_CELL_COUNT],
    const uint32_t occupied[GRID81_CELL_COUNT],
    const hacf_digest *P7_packet_digest,
    const hacf_digest *P7_digit_array_digest,
    const hacf_digest *P7_occupied_mask_digest,
    const hacf_digest *P7_compiler_writable_mask_digest);

/* Compute receipt identity. Domain: "elpis.semantic.trm_mutability.v1" */
int elpis_trm_mutability_identity(
    const elpis_semantic_trm_mutability_v1 *mut, hacf_digest *out);

/* Validate: masks complementary, counts sum to 81, no dual membership. */
int elpis_trm_mutability_validate(
    const elpis_semantic_trm_mutability_v1 *mut);

/* Persistence */
int elpis_write_trm_mutability(const char *path,
    const elpis_semantic_trm_mutability_v1 *mut);
int elpis_read_trm_mutability(const char *path,
    elpis_semantic_trm_mutability_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
