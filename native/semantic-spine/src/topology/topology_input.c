/* topology_input.c — P5 handoff validation and input binding. */
#include "elpis_semantic/topology_graph.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>
static const hacf_digest zero_d = {{0}};

int elpis_topology_validate_handoff(
    const elpis_semantic_downstream_handoff_v1 *handoff,
    const elpis_semantic_bounded_semantic_view_v1 *view) {
    if (!handoff || !view) return SEMANTIC_E_INVAL;

    /* Validate ABI version */
    if (handoff->abi_version != DOWNSTREAM_HANDOFF_ABI_VERSION) return SEMANTIC_E_INVAL;

    /* Validate handoff kind */
    if (handoff->handoff_kind != HANDOFF_KIND_SEMANTIC_TOPOLOGY_COMPILER_INPUT)
        return SEMANTIC_E_INVAL;

    /* Validate bounded view ABI */
    if (view->abi_version != BOUNDED_SEMANTIC_VIEW_ABI_VERSION) return SEMANTIC_E_INVAL;

    /* Check required digests are non-zero */
    if (memcmp(&handoff->root_query_overlay_digest, &zero_d, HACF_DIGEST_BYTES) == 0) return SEMANTIC_E_INVAL;
    if (memcmp(&handoff->bounded_semantic_view_digest, &zero_d, HACF_DIGEST_BYTES) == 0) return SEMANTIC_E_INVAL;
    if (memcmp(&handoff->semantic_plane_digest, &zero_d, HACF_DIGEST_BYTES) == 0) return SEMANTIC_E_INVAL;
    if (memcmp(&handoff->provenance_plane_digest, &zero_d, HACF_DIGEST_BYTES) == 0) return SEMANTIC_E_INVAL;
    if (memcmp(&handoff->metric_plane_digest, &zero_d, HACF_DIGEST_BYTES) == 0) return SEMANTIC_E_INVAL;
    if (memcmp(&handoff->control_plane_digest, &zero_d, HACF_DIGEST_BYTES) == 0) return SEMANTIC_E_INVAL;

    /* Check reserved bytes are zero */
    for (size_t i = 0; i < sizeof(handoff->reserved); i++) {
        if (handoff->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    /* Validate bounded view counts are non-zero for a meaningful compilation */
    if (view->semantic_node_count == 0) return SEMANTIC_E_INVAL;
    if (view->semantic_hyperedge_count == 0) return SEMANTIC_E_INVAL;

    /* Check reserved in bounded view */
    for (size_t i = 0; i < sizeof(view->reserved); i++) {
        if (view->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    return SEMANTIC_OK;
}
