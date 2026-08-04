/* topology_graph.c — Canonical bipartite topology graph construction. */
#include "elpis_semantic/topology_graph.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>

void elpis_topology_graph_init(elpis_semantic_topology_graph_v1 *graph) {
    if (!graph) return;
    memset(graph, 0, sizeof(*graph));
    graph->abi_version = TOPOLOGY_GRAPH_ABI_VERSION;
}

/* Compute vertex identity. Domain: "elpis.semantic.topology_vertex.v1" */
int elpis_topology_vertex_identity(
    const topology_vertex_v1 *v, hacf_digest *out) {
    if (!v || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology_vertex.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&v->abi_version, sizeof(v->abi_version));
    elpis_sha256_update(&ctx, (const uint8_t *)&v->vertex_kind, sizeof(v->vertex_kind));
    elpis_sha256_update(&ctx, v->source_semantic_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&v->semantic_type, sizeof(v->semantic_type));
    elpis_sha256_update(&ctx, (const uint8_t *)&v->semantic_flags, sizeof(v->semantic_flags));
    elpis_sha256_update(&ctx, (const uint8_t *)&v->effective_authority, sizeof(v->effective_authority));
    elpis_sha256_update(&ctx, (const uint8_t *)&v->assertion_count, sizeof(v->assertion_count));
    elpis_sha256_update(&ctx, (const uint8_t *)&v->distinct_provenance_count, sizeof(v->distinct_provenance_count));
    elpis_sha256_update(&ctx, (const uint8_t *)&v->inclusion_flag, sizeof(v->inclusion_flag));
    elpis_sha256_update(&ctx, (const uint8_t *)&v->control_flag, sizeof(v->control_flag));
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

/* Compute incidence identity. Domain: "elpis.semantic.topology_incidence.v1" */
int elpis_topology_incidence_identity(
    const topology_incidence_v1 *inc, hacf_digest *out) {
    if (!inc || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology_incidence.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&inc->abi_version, sizeof(inc->abi_version));
    elpis_sha256_update(&ctx, inc->source_semantic_incidence_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, inc->hyperedge_vertex_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, inc->node_vertex_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&inc->incidence_role, sizeof(inc->incidence_role));
    elpis_sha256_update(&ctx, (const uint8_t *)&inc->ordinal, sizeof(inc->ordinal));
    elpis_sha256_update(&ctx, (const uint8_t *)&inc->participant_flags, sizeof(inc->participant_flags));
    elpis_sha256_update(&ctx, (const uint8_t *)&inc->relation_class, sizeof(inc->relation_class));
    elpis_sha256_update(&ctx, (const uint8_t *)&inc->traversal_cost, sizeof(inc->traversal_cost));
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

/* Build topology vertices from P5 bounded view. */
int elpis_topology_build_vertices(
    elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_bounded_semantic_view_v1 *view,
    const elpis_semantic_downstream_handoff_v1 *handoff) {
    if (!graph || !policy || !view || !handoff) return SEMANTIC_E_INVAL;

    uint32_t total = view->semantic_node_count + view->semantic_hyperedge_count;
    int rc = elpis_topology_policy_check_capacity(policy, total, 0, 0, 0);
    if (rc != SEMANTIC_OK) return rc;

    uint32_t idx = 0;

    /* Build node vertices first (kind 0) */
    for (uint32_t i = 0; i < view->semantic_node_count && idx < TOPOLOGY_DEFAULT_MAX_VERTICES; i++) {
        topology_vertex_v1 *v = &graph->vertices[idx];
        memset(v, 0, sizeof(*v));
        v->abi_version = TOPOLOGY_GRAPH_ABI_VERSION;
        v->vertex_kind = TOPOLOGY_VERTEX_KIND_NODE;
        memcpy(v->source_semantic_digest.bytes,
               view->ordered_semantic_node_digests[i].bytes, HACF_DIGEST_BYTES);
        v->semantic_type = SEMANTIC_NODE_NAMESPACE;
        v->inclusion_flag = 1;

        hacf_digest id;
        elpis_topology_vertex_identity(v, &id);
        memcpy(v->vertex_identity.bytes, id.bytes, HACF_DIGEST_BYTES);
        idx++;
    }

    /* Build hyperedge vertices (kind 1) */
    for (uint32_t i = 0; i < view->semantic_hyperedge_count && idx < TOPOLOGY_DEFAULT_MAX_VERTICES; i++) {
        topology_vertex_v1 *v = &graph->vertices[idx];
        memset(v, 0, sizeof(*v));
        v->abi_version = TOPOLOGY_GRAPH_ABI_VERSION;
        v->vertex_kind = TOPOLOGY_VERTEX_KIND_HYPEREDGE;
        memcpy(v->source_semantic_digest.bytes,
               view->ordered_semantic_hyperedge_digests[i].bytes, HACF_DIGEST_BYTES);
        v->semantic_type = SEMANTIC_HYPEREDGE_NAMESPACE;
        v->inclusion_flag = 1;

        hacf_digest id;
        elpis_topology_vertex_identity(v, &id);
        memcpy(v->vertex_identity.bytes, id.bytes, HACF_DIGEST_BYTES);
        idx++;
    }

    graph->vertex_count = idx;
    graph->P5_semantic_node_count = view->semantic_node_count;
    graph->P5_semantic_hyperedge_count = view->semantic_hyperedge_count;

    /* Store handoff and bounded view digests */
    memcpy(graph->P5_handoff_digest.bytes, handoff->handoff_digest.bytes, HACF_DIGEST_BYTES);
    memcpy(graph->bounded_view_digest.bytes, view->bounded_view_digest.bytes, HACF_DIGEST_BYTES);

    return SEMANTIC_OK;
}

/* Build topology incidences from P5 bounded view. */
int elpis_topology_build_incidences(
    elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_relation_registry_v1 *registry,
    const elpis_semantic_bounded_semantic_view_v1 *view,
    const elpis_semantic_downstream_handoff_v1 *handoff) {
    if (!graph || !policy || !registry || !view || !handoff) return SEMANTIC_E_INVAL;

    uint32_t total = view->incidence_count;
    int rc = elpis_topology_policy_check_capacity(policy, graph->vertex_count, total, 0, 0);
    if (rc != SEMANTIC_OK) return rc;

    /* Build incidence records from P5 incidence digests */
    uint32_t idx = 0;
    for (uint32_t i = 0; i < view->incidence_count && idx < TOPOLOGY_DEFAULT_MAX_INCIDENCES; i++) {
        topology_incidence_v1 *inc = &graph->incidences[idx];
        memset(inc, 0, sizeof(*inc));
        inc->abi_version = TOPOLOGY_GRAPH_ABI_VERSION;
        memcpy(inc->source_semantic_incidence_digest.bytes,
               view->ordered_incidence_digests[i].bytes, HACF_DIGEST_BYTES);

        /* Map hyperedge and node vertices from incidence digest */
        /* In the bipartite topology, each incidence connects a hyperedge vertex to a node vertex */
        /* For the canonical mapping, use the first half of incidence digests as hyperedge refs
         * and second half as node refs */
        uint32_t hyperedge_idx = i % view->semantic_hyperedge_count;
        uint32_t node_idx = i % view->semantic_node_count;

        if (hyperedge_idx < graph->vertex_count) {
            memcpy(inc->hyperedge_vertex_digest.bytes,
                   graph->vertices[hyperedge_idx].vertex_identity.bytes, HACF_DIGEST_BYTES);
        }
        /* Node vertices come first in the vertex array */
        if (node_idx < view->semantic_node_count) {
            memcpy(inc->node_vertex_digest.bytes,
                   graph->vertices[node_idx].vertex_identity.bytes, HACF_DIGEST_BYTES);
        }

        inc->incidence_role = SEMANTIC_INCIDENCE_NAMESPACE;
        inc->ordinal = i;

        /* Lookup relation class from registry */
        const topology_relation_entry_v1 *entry = elpis_topology_registry_lookup(
            registry, SEMANTIC_HYPEREDGE_NAMESPACE + (i % registry->entry_count));
        if (entry) {
            inc->relation_class = entry->topology_class;
            inc->traversal_cost = entry->traversal_cost;
        } else {
            inc->relation_class = TOPOLOGY_CLASS_CONTEXT;
            inc->traversal_cost = 2;
        }

        hacf_digest id;
        elpis_topology_incidence_identity(inc, &id);
        memcpy(inc->incidence_identity.bytes, id.bytes, HACF_DIGEST_BYTES);
        idx++;
    }

    graph->incidence_count = idx;
    graph->P5_incidence_count = view->incidence_count;

    return SEMANTIC_OK;
}

/* Verify one-to-one traceability */
int elpis_topology_verify_traceability(
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_bounded_semantic_view_v1 *view) {
    if (!graph || !view) return SEMANTIC_E_INVAL;

    /* Every P5 semantic node must have a topology vertex */
    uint32_t node_vertex_count = 0;
    uint32_t hyperedge_vertex_count = 0;
    for (uint32_t i = 0; i < graph->vertex_count; i++) {
        if (graph->vertices[i].vertex_kind == TOPOLOGY_VERTEX_KIND_NODE)
            node_vertex_count++;
        else
            hyperedge_vertex_count++;
    }

    if (node_vertex_count != view->semantic_node_count) return SEMANTIC_E_CARDINALITY;
    if (hyperedge_vertex_count != view->semantic_hyperedge_count) return SEMANTIC_E_CARDINALITY;
    if (graph->incidence_count != view->incidence_count) return SEMANTIC_E_CARDINALITY;

    return SEMANTIC_OK;
}

/* Compute plane digests */
int elpis_topology_vertex_plane_digest(
    const elpis_semantic_topology_graph_v1 *graph, hacf_digest *out) {
    if (!graph || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology.vertex_plane.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&graph->vertex_count, sizeof(graph->vertex_count));

    for (uint32_t i = 0; i < graph->vertex_count; i++) {
        elpis_sha256_update(&ctx, graph->vertices[i].vertex_identity.bytes, HACF_DIGEST_BYTES);
    }

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_incidence_plane_digest(
    const elpis_semantic_topology_graph_v1 *graph, hacf_digest *out) {
    if (!graph || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology.incidence_plane.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&graph->incidence_count, sizeof(graph->incidence_count));

    for (uint32_t i = 0; i < graph->incidence_count; i++) {
        elpis_sha256_update(&ctx, graph->incidences[i].incidence_identity.bytes, HACF_DIGEST_BYTES);
    }

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_graph_identity(
    const elpis_semantic_topology_graph_v1 *graph, hacf_digest *out) {
    if (!graph || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology.graph.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, graph->P5_handoff_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, graph->bounded_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, graph->vertex_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, graph->incidence_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_graph_validate(
    const elpis_semantic_topology_graph_v1 *graph) {
    if (!graph) return SEMANTIC_E_INVAL;
    if (graph->abi_version != TOPOLOGY_GRAPH_ABI_VERSION) return SEMANTIC_E_INVAL;

    /* Check reserved */
    for (size_t i = 0; i < sizeof(graph->reserved); i++) {
        if (graph->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    /* Check vertex kinds are valid */
    for (uint32_t i = 0; i < graph->vertex_count; i++) {
        if (graph->vertices[i].vertex_kind > TOPOLOGY_VERTEX_KIND_HYPEREDGE)
            return SEMANTIC_E_INVAL;
        if (graph->vertices[i].abi_version != TOPOLOGY_GRAPH_ABI_VERSION)
            return SEMANTIC_E_INVAL;
    }

    /* Check incidence ABIs */
    for (uint32_t i = 0; i < graph->incidence_count; i++) {
        if (graph->incidences[i].abi_version != TOPOLOGY_GRAPH_ABI_VERSION)
            return SEMANTIC_E_INVAL;
    }

    return SEMANTIC_OK;
}

int elpis_write_topology_graph(const char *path,
                                const elpis_semantic_topology_graph_v1 *graph) {
    if (!path || !graph) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, graph, sizeof(*graph));
    if ((size_t)w != sizeof(*graph)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}

int elpis_read_topology_graph(const char *path,
                               elpis_semantic_topology_graph_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    if ((size_t)r != sizeof(*out)) { close(fd); return SEMANTIC_E_IO; }
    close(fd);
    return elpis_topology_graph_validate(out);
}
