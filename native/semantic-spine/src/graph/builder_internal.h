/* builder_internal.h — Private builder struct layout.
 *
 * Only include from .c files that need internal access.
 * Public consumers should use the opaque typedef from hypergraph.h.
 */
#ifndef ELPIS_SEMANTIC_BUILDER_INTERNAL_H
#define ELPIS_SEMANTIC_BUILDER_INTERNAL_H

#include "elpis_semantic/hypergraph.h"

struct semantic_hypergraph_builder {
    const semantic_type_registry *registry;

    elpis_semantic_node_v1         *nodes;
    uint32_t                       node_count;
    uint32_t                       node_capacity;

    elpis_semantic_assertion_v1    *assertions;
    uint32_t                       assertion_count;
    uint32_t                       assertion_capacity;

    elpis_semantic_hyperedge_v1    *hyperedges;
    uint32_t                       hyperedge_count;
    uint32_t                       hyperedge_capacity;

    elpis_semantic_incidence_v1    *incidences;
    uint32_t                       incidence_count;
    uint32_t                       incidence_capacity;
};

#endif
