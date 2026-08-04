/* elpis_semantic/topology_graph.h — Canonical bipartite topology graph.
 *
 * Represents the P5 semantic hypergraph as a bipartite topology:
 *   semantic-node vertex <-> incidence <-> semantic-hyperedge vertex
 *
 * N-ary hyperedges are preserved as single hyperedge vertices with
 * multiple role-bearing incidences. No pairwise edge invention.
 *
 * Identity domain (vertex): "elpis.semantic.topology_vertex.v1"
 * Identity domain (incidence): "elpis.semantic.topology_incidence.v1"
 */
#ifndef ELPIS_SEMANTIC_TOPOLOGY_GRAPH_H
#define ELPIS_SEMANTIC_TOPOLOGY_GRAPH_H

#include "elpis_semantic/topology_policy.h"
#include "elpis_semantic/topology_registry.h"
#include "elpis_semantic/downstream_handoff.h"
#include "elpis_semantic/bounded_semantic_view.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TOPOLOGY_GRAPH_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Vertex kind                                                           */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_vertex_kind {
    TOPOLOGY_VERTEX_KIND_NODE      = 0,
    TOPOLOGY_VERTEX_KIND_HYPEREDGE = 1,
} topology_vertex_kind;

/* ──────────────────────────────────────────────────────────────────── */
/* Topology vertex — canonical representation of a P5 semantic object   */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct topology_vertex_v1 {
    uint32_t              abi_version;
    uint32_t              vertex_kind;       /* topology_vertex_kind */
    hacf_digest           source_semantic_digest;  /* P5 node/hyperedge digest */
    uint32_t              semantic_type;     /* node_type or hyperedge_type */
    uint32_t              semantic_flags;
    uint32_t              effective_authority;
    uint32_t              assertion_count;
    uint32_t              distinct_provenance_count;
    uint32_t              inclusion_flag;    /* from P5 control plane */
    uint32_t              control_flag;      /* from P5 control plane */
    hacf_digest           vertex_identity;
    uint8_t               reserved[48];
} topology_vertex_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Topology incidence — role-bearing binding                            */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct topology_incidence_v1 {
    uint32_t              abi_version;
    hacf_digest           source_semantic_incidence_digest;
    hacf_digest           hyperedge_vertex_digest;  /* topology vertex digest */
    hacf_digest           node_vertex_digest;       /* topology vertex digest */
    uint32_t              incidence_role;
    uint32_t              ordinal;
    uint32_t              participant_flags;
    uint32_t              relation_class;      /* topology_relation_class */
    uint32_t              traversal_cost;      /* from registry */
    hacf_digest           incidence_identity;
    uint8_t               reserved[32];
} topology_incidence_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Topology graph — collection                                          */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_topology_graph_v1 {
    uint32_t                    abi_version;
    hacf_digest                 P5_handoff_digest;
    hacf_digest                 bounded_view_digest;

    /* Canonical vertices */
    topology_vertex_v1          vertices[TOPOLOGY_DEFAULT_MAX_VERTICES];
    uint32_t                    vertex_count;

    /* Canonical incidences */
    topology_incidence_v1       incidences[TOPOLOGY_DEFAULT_MAX_INCIDENCES];
    uint32_t                    incidence_count;

    /* Traceability counters */
    uint32_t                    P5_semantic_node_count;
    uint32_t                    P5_semantic_hyperedge_count;
    uint32_t                    P5_incidence_count;

    /* Digests */
    hacf_digest                 vertex_plane_digest;
    hacf_digest                 incidence_plane_digest;
    hacf_digest                 graph_identity;
    uint8_t                     reserved[64];
} elpis_semantic_topology_graph_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Operations                                                            */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize empty graph. Sets abi_version, zeroed fields. */
void elpis_topology_graph_init(elpis_semantic_topology_graph_v1 *graph);

/* Validate P5 handoff before compilation. */
int elpis_topology_validate_handoff(
    const elpis_semantic_downstream_handoff_v1 *handoff,
    const elpis_semantic_bounded_semantic_view_v1 *view);

/* Build topology vertices from P5 bounded view. */
int elpis_topology_build_vertices(
    elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_bounded_semantic_view_v1 *view,
    const elpis_semantic_downstream_handoff_v1 *handoff);

/* Build topology incidences from P5 bounded view. */
int elpis_topology_build_incidences(
    elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_relation_registry_v1 *registry,
    const elpis_semantic_bounded_semantic_view_v1 *view,
    const elpis_semantic_downstream_handoff_v1 *handoff);

/* Verify one-to-one traceability: every P5 object mapped, none invented. */
int elpis_topology_verify_traceability(
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_bounded_semantic_view_v1 *view);

/* Compute vertex identity. Domain: "elpis.semantic.topology_vertex.v1" */
int elpis_topology_vertex_identity(
    const topology_vertex_v1 *v, hacf_digest *out);

/* Compute incidence identity. Domain: "elpis.semantic.topology_incidence.v1" */
int elpis_topology_incidence_identity(
    const topology_incidence_v1 *inc, hacf_digest *out);

/* Compute plane digests. */
int elpis_topology_vertex_plane_digest(
    const elpis_semantic_topology_graph_v1 *graph, hacf_digest *out);
int elpis_topology_incidence_plane_digest(
    const elpis_semantic_topology_graph_v1 *graph, hacf_digest *out);

/* Compute graph identity. */
int elpis_topology_graph_identity(
    const elpis_semantic_topology_graph_v1 *graph, hacf_digest *out);

/* Validate graph: traceability, capacity, no pairwise invention. */
int elpis_topology_graph_validate(
    const elpis_semantic_topology_graph_v1 *graph);

/* Persistence */
int elpis_write_topology_graph(const char *path,
                                const elpis_semantic_topology_graph_v1 *graph);
int elpis_read_topology_graph(const char *path,
                               elpis_semantic_topology_graph_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
