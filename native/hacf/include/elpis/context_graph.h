/* elpis/context_graph.h - immutable bounded contextual graph snapshot (Gate R3).
 *
 * This is deliberately not a mutable knowledge-graph database. It is a compact,
 * immutable adjacency snapshot used only for deterministic one-hop expansion
 * after lexical+dense fusion. Input order never affects the snapshot digest or
 * neighbor order. */
#ifndef ELPIS_CONTEXT_GRAPH_H
#define ELPIS_CONTEXT_GRAPH_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ELPIS_CGRAPH_ABI_VERSION 1u
#define ELPIS_CGRAPH_MAX_EDGES   1000000u

typedef struct elpis_context_graph elpis_context_graph;

typedef struct elpis_context_edge_input {
    char     subject_chunk_digest[65];
    char     object_chunk_digest[65];
    char     provenance_digest[65];
    uint32_t edge_type;      /* nonzero application-defined edge type */
    uint32_t authority;      /* hacf_authority numeric value: 0..3 */
} elpis_context_edge_input;

typedef struct elpis_context_neighbor {
    char     chunk_digest[65];
    char     provenance_digest[65];
    uint32_t edge_type;
    uint32_t authority;
} elpis_context_neighbor;

/* Build an immutable directed graph. Exact duplicate edges are collapsed.
 * Self-edges are rejected. All digests must be canonical lowercase hex. */
int  elpis_context_graph_create(const elpis_context_edge_input *edges, uint32_t edge_count,
                                elpis_context_graph **out);
void elpis_context_graph_destroy(elpis_context_graph *g);
const char *elpis_context_graph_error(const elpis_context_graph *g);

uint32_t elpis_context_graph_edge_count(const elpis_context_graph *g);
int elpis_context_graph_digest(const elpis_context_graph *g, char out[65]);

/* Deterministic outgoing neighbors for subject. Results are ordered by:
 * edge_type, object chunk digest, provenance digest, authority. Authority below
 * min_authority is excluded before the limit is applied. */
int elpis_context_graph_neighbors(const elpis_context_graph *g, const char *subject_chunk_digest,
                                  uint32_t min_authority, uint32_t offset, uint32_t limit,
                                  elpis_context_neighbor *out, uint32_t *n_out);

/* Canonical manifest, malloc-owned; release with elpis_free(). */
int elpis_context_graph_manifest_json(const elpis_context_graph *g,
                                      char **json_out, char digest_out[65]);

#ifdef __cplusplus
}
#endif
#endif
