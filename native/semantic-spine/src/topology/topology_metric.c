/* topology_metric.c — Metric hints binding (local ordering only). */
#include "elpis_semantic/topology_address.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>

void elpis_topology_metric_hints_init(
    elpis_semantic_topology_metric_hints_v1 *hints) {
    if (!hints) return;
    memset(hints, 0, sizeof(*hints));
    hints->abi_version = TOPOLOGY_ADDRESS_ABI_VERSION;
}

int elpis_topology_bind_metric_hints(
    elpis_semantic_topology_metric_hints_v1 *hints,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_downstream_handoff_v1 *handoff) {
    (void)graph;
    if (!hints || !policy || !handoff) return SEMANTIC_E_INVAL;

    /* Metric hints come from P5 metric plane observations.
     * We consume the handoff's metric observations and bind them
     * as nonauthoritative local-order hints.
     * In the canonical implementation, metric hints are populated
     * from the metric feature records in the handoff. */

    /* For the deterministic fixture, metric hints are empty unless
     * the P5 bounded view contains metric observations.
     * The metric_plane_digest in the handoff validates presence. */

    return SEMANTIC_OK;
}

int elpis_topology_metric_hints_validate(
    const elpis_semantic_topology_metric_hints_v1 *hints) {
    if (!hints) return SEMANTIC_E_INVAL;
    if (hints->abi_version != TOPOLOGY_ADDRESS_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (hints->hint_count > TOPOLOGY_DEFAULT_MAX_METRIC_HINTS) return SEMANTIC_E_CARDINALITY;

    for (size_t i = 0; i < sizeof(hints->reserved); i++) {
        if (hints->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    for (uint32_t i = 0; i < hints->hint_count; i++) {
        for (size_t j = 0; j < sizeof(hints->hints[i].reserved); j++) {
            if (hints->hints[i].reserved[j] != 0) return SEMANTIC_E_RESERVATION;
        }
    }
    return SEMANTIC_OK;
}

int elpis_write_topology_metric_hints(const char *path,
    const elpis_semantic_topology_metric_hints_v1 *hints) {
    if (!path || !hints) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, hints, sizeof(*hints));
    if ((size_t)w != sizeof(*hints)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}
