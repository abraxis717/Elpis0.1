/* topology_conflict.c — Conflict preservation. */
#include "elpis_semantic/topology_address.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>

void elpis_topology_conflicts_init(elpis_semantic_topology_conflicts_v1 *conflicts) {
    if (!conflicts) return;
    memset(conflicts, 0, sizeof(*conflicts));
    conflicts->abi_version = TOPOLOGY_ADDRESS_ABI_VERSION;
}

int elpis_topology_compile_conflicts(
    elpis_semantic_topology_conflicts_v1 *conflicts,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_relation_registry_v1 *registry,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_downstream_handoff_v1 *handoff) {
    (void)policy; (void)handoff;
    if (!conflicts || !registry || !graph) return SEMANTIC_E_INVAL;

    /* Scan incidences for SUPPORTS and CONTRADICTS relations */
    for (uint32_t i = 0; i < graph->incidence_count; i++) {
        const topology_incidence_v1 *inc = &graph->incidences[i];

        /* Find the relation entry */
        const topology_relation_entry_v1 *entry = NULL;
        for (uint32_t r = 0; r < registry->entry_count; r++) {
            if (registry->entries[r].topology_class == inc->relation_class) {
                entry = &registry->entries[r];
                break;
            }
        }
        if (!entry) continue;

        /* If this is a SUPPORTS or CONTRADICTS relation, record conflict */
        if (entry->polarity != TOPOLOGY_POLARITY_SUPPORT &&
            entry->polarity != TOPOLOGY_POLARITY_CONTRADICTION) {
            continue;
        }

        /* Find or create conflict record for this target */
        uint32_t conflict_idx = conflicts->conflict_count;
        for (uint32_t c = 0; c < conflicts->conflict_count; c++) {
            if (hacf_digest_cmp(&conflicts->conflicts[c].conflict_target_vertex,
                                 &inc->node_vertex_digest) == 0) {
                conflict_idx = c;
                break;
            }
        }

        topology_conflict_record_v1 *rec = &conflicts->conflicts[conflict_idx];
        if (conflict_idx == conflicts->conflict_count) {
            /* New conflict record */
            memset(rec, 0, sizeof(*rec));
            memcpy(&rec->conflict_target_vertex, &inc->node_vertex_digest, HACF_DIGEST_BYTES);
            rec->conflict_status = TOPOLOGY_CONFLICT_UNRESOLVED_PRESERVED;
            conflicts->conflict_count++;
        }

        if (entry->polarity == TOPOLOGY_POLARITY_SUPPORT) {
            if (rec->support_edge_count < sizeof(rec->support_edges) / sizeof(rec->support_edges[0])) {
                memcpy(&rec->support_edges[rec->support_edge_count],
                       &inc->source_semantic_incidence_digest, HACF_DIGEST_BYTES);
                rec->support_edge_count++;
            }
        } else if (entry->polarity == TOPOLOGY_POLARITY_CONTRADICTION) {
            if (rec->contradiction_edge_count < sizeof(rec->contradiction_edges) / sizeof(rec->contradiction_edges[0])) {
                memcpy(&rec->contradiction_edges[rec->contradiction_edge_count],
                       &inc->source_semantic_incidence_digest, HACF_DIGEST_BYTES);
                rec->contradiction_edge_count++;
            }
        }
    }

    return SEMANTIC_OK;
}

int elpis_topology_conflicts_validate(
    const elpis_semantic_topology_conflicts_v1 *conflicts) {
    if (!conflicts) return SEMANTIC_E_INVAL;
    if (conflicts->abi_version != TOPOLOGY_ADDRESS_ABI_VERSION) return SEMANTIC_E_INVAL;

    for (size_t i = 0; i < sizeof(conflicts->reserved); i++) {
        if (conflicts->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    for (uint32_t i = 0; i < conflicts->conflict_count; i++) {
        const topology_conflict_record_v1 *rec = &conflicts->conflicts[i];
        if (rec->conflict_status != TOPOLOGY_CONFLICT_UNRESOLVED_PRESERVED)
            return SEMANTIC_E_INVAL;
        for (size_t j = 0; j < sizeof(rec->reserved); j++) {
            if (rec->reserved[j] != 0) return SEMANTIC_E_RESERVATION;
        }
    }
    return SEMANTIC_OK;
}

int elpis_write_topology_conflicts(const char *path,
    const elpis_semantic_topology_conflicts_v1 *conflicts) {
    if (!path || !conflicts) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, conflicts, sizeof(*conflicts));
    if ((size_t)w != sizeof(*conflicts)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}
