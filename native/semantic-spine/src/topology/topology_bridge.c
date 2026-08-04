/* topology_bridge.c — Cross-constellation bridge detection. */
#include "elpis_semantic/topology_address.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>

void elpis_topology_bridges_init(elpis_semantic_topology_bridges_v1 *bridges) {
    if (!bridges) return;
    memset(bridges, 0, sizeof(*bridges));
    bridges->abi_version = TOPOLOGY_ADDRESS_ABI_VERSION;
}

int elpis_topology_compile_bridges(
    elpis_semantic_topology_bridges_v1 *bridges,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_constellations_v1 *constellations) {
    (void)policy;
    if (!bridges || !graph || !constellations) return SEMANTIC_E_INVAL;

    /* Check each incidence: if the hyperedge connects nodes in different constellations, bridge */
    for (uint32_t i = 0; i < graph->incidence_count; i++) {
        const topology_incidence_v1 *inc = &graph->incidences[i];

        int node_constellation = elpis_topology_find_constellation(constellations, &inc->node_vertex_digest);
        int he_constellation = -1;

        /* Check if the hyperedge vertex itself has a primary constellation */
        for (uint32_t c = 0; c < constellations->constellation_count; c++) {
            for (uint32_t m = 0; m < constellations->constellations[c].primary_member_count; m++) {
                if (hacf_digest_cmp(&constellations->constellations[c].primary_members[m],
                                     &inc->hyperedge_vertex_digest) == 0) {
                    he_constellation = (int)c;
                    break;
                }
            }
            if (he_constellation >= 0) break;
        }

        if (node_constellation >= 0 && he_constellation >= 0 && node_constellation != he_constellation) {
            if (bridges->bridge_count < TOPOLOGY_DEFAULT_MAX_BRIDGES) {
                topology_bridge_record_v1 *br = &bridges->bridges[bridges->bridge_count++];
                memset(br, 0, sizeof(*br));
                memcpy(&br->source_vertex_digest, &inc->node_vertex_digest, HACF_DIGEST_BYTES);
                memcpy(&br->source_hyperedge_digest, &inc->hyperedge_vertex_digest, HACF_DIGEST_BYTES);
                br->bridge_reason = TOPOLOGY_BRIDGE_HYPEREDGE_CROSS_CONSTELLATION;
                br->constellation_count = 2;
                br->constellation_indices[0] = (uint32_t)node_constellation;
                br->constellation_indices[1] = (uint32_t)he_constellation;
            }
        }
    }

    /* Check affiliations for equal-best bridges */
    for (uint32_t a = 0; a < constellations->affiliation_count; a++) {
        const topology_affiliation_v1 *aff = &constellations->affiliations[a];
        if (aff->affiliation_kind != TOPOLOGY_AFFILIATION_SECONDARY) continue;

        /* Check if this vertex has multiple primary-like affiliations */
        uint32_t same_vertex_count = 0;
        uint32_t constellation_list[TOPOLOGY_DEFAULT_MAX_CONSTELLATIONS];
        for (uint32_t a2 = 0; a2 < constellations->affiliation_count; a2++) {
            if (hacf_digest_cmp(&constellations->affiliations[a2].vertex_digest,
                                 &aff->vertex_digest) == 0 &&
                constellations->affiliations[a2].affiliation_kind == TOPOLOGY_AFFILIATION_PRIMARY) {
                constellation_list[same_vertex_count++] = a2;
            }
        }

        if (same_vertex_count >= 2 && bridges->bridge_count < TOPOLOGY_DEFAULT_MAX_BRIDGES) {
            topology_bridge_record_v1 *br = &bridges->bridges[bridges->bridge_count++];
            memset(br, 0, sizeof(*br));
            memcpy(&br->source_vertex_digest, &aff->vertex_digest, HACF_DIGEST_BYTES);
            br->bridge_reason = TOPOLOGY_BRIDGE_EQUAL_BEST_AFFILIATION;
            br->constellation_count = same_vertex_count;
            for (uint32_t c = 0; c < same_vertex_count; c++) {
                br->constellation_indices[c] = constellation_list[c];
            }
        }
    }

    return SEMANTIC_OK;
}

int elpis_topology_bridges_validate(
    const elpis_semantic_topology_bridges_v1 *bridges) {
    if (!bridges) return SEMANTIC_E_INVAL;
    if (bridges->abi_version != TOPOLOGY_ADDRESS_ABI_VERSION) return SEMANTIC_E_INVAL;

    for (size_t i = 0; i < sizeof(bridges->reserved); i++) {
        if (bridges->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    for (uint32_t i = 0; i < bridges->bridge_count; i++) {
        const topology_bridge_record_v1 *br = &bridges->bridges[i];
        if (br->bridge_reason > TOPOLOGY_BRIDGE_CONFLICT_SPAN) return SEMANTIC_E_INVAL;
        if (br->constellation_count == 0) return SEMANTIC_E_INVAL;
        for (size_t j = 0; j < sizeof(br->reserved); j++) {
            if (br->reserved[j] != 0) return SEMANTIC_E_RESERVATION;
        }
    }
    return SEMANTIC_OK;
}

int elpis_write_topology_bridges(const char *path,
    const elpis_semantic_topology_bridges_v1 *bridges) {
    if (!path || !bridges) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, bridges, sizeof(*bridges));
    if ((size_t)w != sizeof(*bridges)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}
