/* grid81_place.c — Deterministic Grid81 cell placement. */
#include "elpis_semantic/grid81_codebook.h"
#include "elpis_semantic/grid81_capsule.h"
#include "elpis_semantic/grid81_cell.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

/* Compute cell placement for a capsule.
 * Column comes from lane codebook only.
 * Row = (primary_constellation_index + semantic_stratum) mod 9.
 */
int elpis_grid81_compute_placement(
    const elpis_semantic_grid81_codebook_v1 *codebook,
    const elpis_semantic_grid81_capsule_v1 *capsule,
    uint32_t *out_row,
    uint32_t *out_col,
    uint32_t *out_cell) {
    if (!codebook || !capsule || !out_row || !out_col || !out_cell) return SEMANTIC_E_INVAL;

    /* Column from lane only */
    uint32_t col;
    int rc = elpis_grid81_codebook_lookup(codebook, capsule->primary_lane, &col);
    if (rc != SEMANTIC_OK) return SEMANTIC_E_INVAL;
    *out_col = col;

    /* Row from constellation + stratum with overflow check */
    uint64_t sum64 = (uint64_t)capsule->primary_constellation_index + (uint64_t)capsule->semantic_stratum;
    uint32_t row = (uint32_t)(sum64 % 9u);
    *out_row = row;

    *out_cell = row * 9u + col;
    if (*out_cell >= GRID81_CELL_COUNT) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

/* Compute digit for a cell given capsule count and row/col.
 * If capsule_count == 0 -> digit = 0 (empty).
 * If capsule_count > 0 -> digit = canonical_template_digit(row, col).
 */
uint32_t elpis_grid81_compute_digit(uint32_t capsule_count, uint32_t row, uint32_t col) {
    if (capsule_count == 0) return 0u;
    return 1u + ((row * 3u + row / 3u + col) % 9u);
}

/* Canonical capsule ordering comparator (for sorting capsules within a cell).
 * Returns <0 if a precedes b, >0 if b precedes a, 0 if equal.
 */
int elpis_grid81_capsule_order_cmp(
    const elpis_semantic_grid81_capsule_v1 *a,
    const elpis_semantic_grid81_capsule_v1 *b) {
    /* mandatory before optional */
    if (a->mandatory_capsule > b->mandatory_capsule) return -1;
    if (a->mandatory_capsule < b->mandatory_capsule) return 1;
    /* lower semantic stratum first */
    if (a->semantic_stratum < b->semantic_stratum) return -1;
    if (a->semantic_stratum > b->semantic_stratum) return 1;
    /* lower primary role first */
    if (a->primary_role < b->primary_role) return -1;
    if (a->primary_role > b->primary_role) return 1;
    /* lower relation-family first */
    if (a->relation_family_class < b->relation_family_class) return -1;
    if (a->relation_family_class > b->relation_family_class) return 1;
    /* conflict-preservation capsule first */
    if (a->conflict_membership > 0 && b->conflict_membership == 0) return -1;
    if (a->conflict_membership == 0 && b->conflict_membership > 0) return 1;
    /* bridge capsule first */
    if (a->bridge_membership > 0 && b->bridge_membership == 0) return -1;
    if (a->bridge_membership == 0 && b->bridge_membership > 0) return 1;
    /* cluster key digest */
    return memcmp(a->cluster_key_digest.bytes, b->cluster_key_digest.bytes, HACF_DIGEST_BYTES);
}
