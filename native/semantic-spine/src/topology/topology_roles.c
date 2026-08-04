/* topology_roles.c — Role and lane assignment. */
#include "elpis_semantic/topology_address.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>

void elpis_topology_roles_init(elpis_semantic_topology_roles_v1 *roles) {
    if (!roles) return;
    memset(roles, 0, sizeof(*roles));
    roles->abi_version = TOPOLOGY_ADDRESS_ABI_VERSION;
}

int elpis_topology_assign_roles(
    elpis_semantic_topology_roles_v1 *roles,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_relation_registry_v1 *registry,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_anchors_v1 *anchors,
    const elpis_semantic_bounded_semantic_view_v1 *view,
    const elpis_semantic_downstream_handoff_v1 *handoff) {
    (void)policy; (void)registry; (void)view; (void)handoff;
    if (!roles || !graph || !anchors) return SEMANTIC_E_INVAL;

    uint32_t idx = 0;
    for (uint32_t v = 0; v < graph->vertex_count; v++) {
        const topology_vertex_v1 *vert = &graph->vertices[v];
        topology_role_assignment_v1 *ra = &roles->assignments[idx++];
        memset(ra, 0, sizeof(*ra));

        memcpy(&ra->vertex_digest, &vert->vertex_identity, HACF_DIGEST_BYTES);

        /* Primary role precedence */
        /* 1. QUERY_CORE */
        if (elpis_topology_find_anchor(anchors, &vert->vertex_identity)) {
            if (elpis_topology_find_anchor(anchors, &vert->vertex_identity)->source_kind ==
                TOPOLOGY_ANCHOR_SOURCE_QUERY) {
                ra->primary_role = TOPOLOGY_ROLE_QUERY_CORE;
                ra->role_flags |= TOPOLOGY_ROLE_FLAG_ANCHOR;
                ra->lane = TOPOLOGY_LANE_CORE;
            }
            /* 3. REQUIREMENT_TARGET */
            else if (elpis_topology_find_anchor(anchors, &vert->vertex_identity)->source_kind ==
                     TOPOLOGY_ANCHOR_SOURCE_REQUIREMENT_TARGET) {
                ra->primary_role = TOPOLOGY_ROLE_REQUIREMENT_TARGET;
                ra->role_flags |= TOPOLOGY_ROLE_FLAG_ANCHOR;
                ra->lane = TOPOLOGY_LANE_CORE;
            }
            /* 3. REQUIREMENT_WITNESS */
            else if (elpis_topology_find_anchor(anchors, &vert->vertex_identity)->source_kind ==
                     TOPOLOGY_ANCHOR_SOURCE_REQUIREMENT_WITNESS) {
                ra->primary_role = TOPOLOGY_ROLE_REQUIREMENT_WITNESS;
                ra->role_flags |= TOPOLOGY_ROLE_FLAG_ANCHOR;
                ra->lane = TOPOLOGY_LANE_QUALIFIER;
            }
            /* 4. CONFLICT_TARGET */
            else if (elpis_topology_find_anchor(anchors, &vert->vertex_identity)->source_kind ==
                     TOPOLOGY_ANCHOR_SOURCE_CONFLICT_TARGET) {
                ra->primary_role = TOPOLOGY_ROLE_CONFLICT_TARGET;
                ra->role_flags |= TOPOLOGY_ROLE_FLAG_ANCHOR | TOPOLOGY_ROLE_FLAG_CONFLICT_TARGET;
                ra->lane = TOPOLOGY_LANE_CORE;
            }
            else {
                ra->primary_role = TOPOLOGY_ROLE_NEUTRAL;
                ra->lane = TOPOLOGY_LANE_NEUTRAL;
            }
        }
        /* Default by vertex kind */
        else if (vert->vertex_kind == TOPOLOGY_VERTEX_KIND_HYPEREDGE) {
            ra->primary_role = TOPOLOGY_ROLE_RELATION_HUB;
            ra->lane = TOPOLOGY_LANE_NEUTRAL;
        }
        else {
            ra->primary_role = TOPOLOGY_ROLE_CONTEXT;
            ra->lane = TOPOLOGY_LANE_CONTEXT;
        }

        ra->stratum = 0; /* Will be refined by constellation assignment */
    }

    roles->assignment_count = idx;
    return SEMANTIC_OK;
}

int elpis_topology_roles_validate(const elpis_semantic_topology_roles_v1 *roles) {
    if (!roles) return SEMANTIC_E_INVAL;
    if (roles->abi_version != TOPOLOGY_ADDRESS_ABI_VERSION) return SEMANTIC_E_INVAL;

    for (size_t i = 0; i < sizeof(roles->reserved); i++) {
        if (roles->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    for (uint32_t i = 0; i < roles->assignment_count; i++) {
        const topology_role_assignment_v1 *ra = &roles->assignments[i];
        if (ra->primary_role > TOPOLOGY_ROLE_NEUTRAL) return SEMANTIC_E_INVAL;
        if (ra->lane > TOPOLOGY_LANE_NEUTRAL) return SEMANTIC_E_INVAL;
        if (ra->role_flags & ~TOPOLOGY_ROLE_FLAG_MASK) return SEMANTIC_E_RESERVATION;
        for (size_t j = 0; j < sizeof(ra->reserved); j++) {
            if (ra->reserved[j] != 0) return SEMANTIC_E_RESERVATION;
        }
    }
    return SEMANTIC_OK;
}

int elpis_write_topology_roles(const char *path,
    const elpis_semantic_topology_roles_v1 *roles) {
    if (!path || !roles) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, roles, sizeof(*roles));
    if ((size_t)w != sizeof(*roles)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}
