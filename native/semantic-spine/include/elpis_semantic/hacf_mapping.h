/* elpis_semantic/hacf_mapping.h — Semantic-to-HACF graph operation mapping. */
#ifndef ELPIS_SEMANTIC_HACF_MAPPING_H
#define ELPIS_SEMANTIC_HACF_MAPPING_H

#include "elpis_semantic/hypergraph.h"
#include "elpis/graph.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

int semantic_map_to_hacf_ops(const semantic_hypergraph_builder *builder,
                               hacf_graph_op **ops_out, uint32_t *op_count_out);
void semantic_free_hacf_ops(hacf_graph_op *ops);
int semantic_compute_hacf_delta(const hacf_digest *prior_snapshot,
                                 const hacf_graph_op *ops, uint32_t op_count,
                                 hacf_digest *delta_digest_out,
                                 hacf_digest *next_snapshot_out);

#ifdef __cplusplus
}
#endif
#endif
