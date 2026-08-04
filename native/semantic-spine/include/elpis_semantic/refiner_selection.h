/* elpis_semantic/refiner_selection.h — Qualification and selection v1.
 *
 * Identity domain: "elpis.semantic.refiner_selection.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINER_SELECTION_H
#define ELPIS_SEMANTIC_REFINER_SELECTION_H

#include "elpis_semantic/refiner_candidate.h"
#include "elpis_semantic/refiner_metrics.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINER_SELECTION_VERSION 1u
#define REFINER_MAX_RANKING 8u

typedef struct elpis_semantic_refiner_selection_v1 {
    uint32_t                              abi_version;
    uint32_t                              qualified_count;
    uint32_t                              ranking_count;

    /* Ranked candidate names (lexicographic order per bakeoff policy) */
    char                                  ranking[REFINER_MAX_RANKING][REFINER_CANDIDATE_NAME_MAX];

    /* Selected winner */
    char                                  selected_name[REFINER_CANDIDATE_NAME_MAX];
    uint8_t                               selection_valid;

    hacf_digest                           selection_digest;
    uint8_t                               reserved[64];
} elpis_semantic_refiner_selection_v1;

void elpis_refiner_selection_init(elpis_semantic_refiner_selection_v1 *sel);
int elpis_refiner_selection_identity(const elpis_semantic_refiner_selection_v1 *sel,
    hacf_digest *out);
int elpis_refiner_selection_validate(const elpis_semantic_refiner_selection_v1 *sel);

int elpis_write_refiner_selection(const char *path,
    const elpis_semantic_refiner_selection_v1 *sel);
int elpis_read_refiner_selection(const char *path,
    elpis_semantic_refiner_selection_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
