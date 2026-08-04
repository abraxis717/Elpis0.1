/* elpis_semantic/grid81_codebook.h — Fixed semantic-to-column codebook v1.
 *
 * Maps P6 topology lanes to Grid81 columns. Lane determines column only.
 * The Grid81 digit assigned to a cell comes from the Sudoku template,
 * never from this codebook.
 *
 * Identity domain: "elpis.semantic.grid81_codebook.v1"
 */
#ifndef ELPIS_SEMANTIC_GRID81_CODEBOOK_H
#define ELPIS_SEMANTIC_GRID81_CODEBOOK_H

#include "elpis_semantic/topology_registry.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define GRID81_CODEBOOK_ABI_VERSION 1u
#define GRID81_CODEBOOK_LANE_COUNT  10u

/* ──────────────────────────────────────────────────────────────────── */
/* Codebook entry                                                       */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct grid81_codebook_entry_v1 {
    uint32_t      lane;       /* topology_lane value */
    uint32_t      column;     /* Grid81 column (0-8) */
    uint8_t       reserved[32];
} grid81_codebook_entry_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Codebook record                                                      */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_grid81_codebook_v1 {
    uint32_t                          abi_version;

    grid81_codebook_entry_v1          entries[GRID81_CODEBOOK_LANE_COUNT];
    uint32_t                          entry_count;

    /* Column separation guarantees */
    uint32_t                          support_contradiction_distinct;   /* 1 */
    uint32_t                          qualifier_scope_distinct;        /* 1 */
    uint32_t                          bridge_context_distinct;         /* 1 */

    /* Nonauthority flags */
    uint32_t                          lane_does_not_determine_digit;   /* 1 */
    uint32_t                          column_does_not_encode_semantic; /* 1 */

    hacf_digest                       codebook_digest;

    uint8_t                           reserved[64];
} elpis_semantic_grid81_codebook_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                           */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize with the fixed lane-to-column mapping. */
void elpis_grid81_codebook_init(elpis_semantic_grid81_codebook_v1 *codebook);

/* Look up column for a lane. Returns SEMANTIC_OK or SEMANTIC_E_INVAL
 * for unknown lane. */
int elpis_grid81_codebook_lookup(
    const elpis_semantic_grid81_codebook_v1 *codebook,
    uint32_t lane,
    uint32_t *out_column);

/* Compute identity digest. Domain: "elpis.semantic.grid81_codebook.v1" */
int elpis_grid81_codebook_identity(
    const elpis_semantic_grid81_codebook_v1 *codebook, hacf_digest *out);

/* Validate: ABI, all 10 lanes mapped, separation guarantees, flags set. */
int elpis_grid81_codebook_validate(
    const elpis_semantic_grid81_codebook_v1 *codebook);

/* Persistence */
int elpis_write_grid81_codebook(const char *path,
    const elpis_semantic_grid81_codebook_v1 *codebook);
int elpis_read_grid81_codebook(const char *path,
    elpis_semantic_grid81_codebook_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
