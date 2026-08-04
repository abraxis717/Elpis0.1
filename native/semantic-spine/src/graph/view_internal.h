/* view_internal.h — Private snapshot view struct layout.
 *
 * Only include from .c files that need internal access.
 */
#ifndef ELPIS_SEMANTIC_VIEW_INTERNAL_H
#define ELPIS_SEMANTIC_VIEW_INTERNAL_H

#include "elpis_semantic/snapshot_view.h"

struct semantic_snapshot_view {
    const semantic_snapshot_manifest *manifest;
    elpis_semantic_node_v1         *nodes;
    uint32_t                       node_count;
    elpis_semantic_assertion_v1    *assertions;
    uint32_t                       assertion_count;
    elpis_semantic_hyperedge_v1    *hyperedges;
    uint32_t                       hyperedge_count;
    elpis_semantic_incidence_v1    *incidences;
    uint32_t                       incidence_count;
};

#endif
