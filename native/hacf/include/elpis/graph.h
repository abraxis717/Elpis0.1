#ifndef ELPIS_GRAPH_H
#define ELPIS_GRAPH_H
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef enum hacf_graph_op_type { HACF_GRAPH_ADD_NODE=1, HACF_GRAPH_ADD_EDGE=2 } hacf_graph_op_type;

typedef struct hacf_graph_op {
    uint32_t type;
    uint32_t node_or_edge_type;
    hacf_digest subject;
    hacf_digest object;
    hacf_digest provenance;
    uint32_t authority;
} hacf_graph_op;

int hacf_graph_delta_digest(const hacf_digest *prior_snapshot,
                            const hacf_graph_op *ops, uint32_t op_count,
                            hacf_digest *delta_digest,
                            hacf_digest *next_snapshot);
#ifdef __cplusplus
}
#endif
#endif
