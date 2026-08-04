/* refiner_inventory.c — Local candidate inventory scanning. */
#include "elpis_semantic/refiner_candidate.h"
#include <string.h>

/* Inventory is computed in the Python bakeoff runner (tools/refiner/).
 * This module provides the C-side data structures for downstream consumers.
 * See P11_CANDIDATE_INVENTORY.json for the authoritative inventory. */

int elpis_refiner_inventory_load_candidates(
    const char *inventory_path,
    elpis_semantic_refiner_candidate_v1 *candidates,
    uint32_t max_candidates,
    uint32_t *out_count) {
    /* Stub — JSON deserialization delegated to tools/refiner/run_p11_bakeoff.py */
    (void)inventory_path;
    (void)candidates;
    (void)max_candidates;
    *out_count = 0;
    return SEMANTIC_OK;
}
