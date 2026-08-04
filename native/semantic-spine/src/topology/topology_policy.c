/* elpis_semantic/topology_policy.c — Immutable topology policy v1. */
#include "elpis_semantic/topology_policy.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>

void elpis_topology_policy_init(elpis_semantic_topology_policy_v1 *policy) {
    if (!policy) return;
    memset(policy, 0, sizeof(*policy));
    policy->abi_version = TOPOLOGY_POLICY_ABI_VERSION;
    policy->max_vertices = TOPOLOGY_DEFAULT_MAX_VERTICES;
    policy->max_incidences = TOPOLOGY_DEFAULT_MAX_INCIDENCES;
    policy->max_anchors = TOPOLOGY_DEFAULT_MAX_ANCHORS;
    policy->max_constellations = TOPOLOGY_DEFAULT_MAX_CONSTELLATIONS;
    policy->max_affiliations_per_vertex = TOPOLOGY_DEFAULT_MAX_AFFILIATIONS;
    policy->max_semantic_path_cost = TOPOLOGY_DEFAULT_MAX_PATH_COST;
    policy->max_semantic_path_hops = TOPOLOGY_DEFAULT_MAX_PATH_HOPS;
    policy->max_bridges = TOPOLOGY_DEFAULT_MAX_BRIDGES;
    policy->max_metric_hints = TOPOLOGY_DEFAULT_MAX_METRIC_HINTS;
    policy->unanchored_behavior = TOPOLOGY_UNANCHORED_FAIL_CLOSED;
    policy->capacity_overflow_behavior = TOPOLOGY_CAPACITY_OVERFLOW_FAIL_CLOSED;
    policy->conflict_policy = TOPOLOGY_CONFLICT_PRESERVE_BOTH;
    policy->transport_policy = TOPOLOGY_TRANSPORT_TRACE_ONLY;
    policy->metric_policy = TOPOLOGY_METRIC_LOCAL_ORDER_ONLY;
    policy->flags = TOPOLOGY_POLICY_FLAG_NONE;
}

int elpis_topology_policy_identity(
    const elpis_semantic_topology_policy_v1 *policy, hacf_digest *out) {
    if (!policy || !out) return SEMANTIC_E_INVAL;
    /* Domain: "elpis.semantic.topology_policy.v1" */
    const char domain[] = "elpis.semantic.topology_policy.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);

    uint32_t be;
    memcpy(&be, &policy->abi_version, sizeof(be));
    /* Already host-endian; identity uses raw bytes for determinism within host */
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->abi_version, sizeof(policy->abi_version));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->max_vertices, sizeof(policy->max_vertices));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->max_incidences, sizeof(policy->max_incidences));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->max_anchors, sizeof(policy->max_anchors));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->max_constellations, sizeof(policy->max_constellations));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->max_affiliations_per_vertex, sizeof(policy->max_affiliations_per_vertex));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->max_semantic_path_cost, sizeof(policy->max_semantic_path_cost));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->max_semantic_path_hops, sizeof(policy->max_semantic_path_hops));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->max_bridges, sizeof(policy->max_bridges));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->max_metric_hints, sizeof(policy->max_metric_hints));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->unanchored_behavior, sizeof(policy->unanchored_behavior));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->capacity_overflow_behavior, sizeof(policy->capacity_overflow_behavior));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->conflict_policy, sizeof(policy->conflict_policy));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->transport_policy, sizeof(policy->transport_policy));
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->metric_policy, sizeof(policy->metric_policy));
    elpis_sha256_update(&ctx, policy->address_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->constraint_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&policy->flags, sizeof(policy->flags));

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_policy_validate(
    const elpis_semantic_topology_policy_v1 *policy) {
    if (!policy) return SEMANTIC_E_INVAL;
    if (policy->abi_version != TOPOLOGY_POLICY_ABI_VERSION) return SEMANTIC_E_INVAL;

    /* Check reserved bytes are zero */
    for (size_t i = 0; i < sizeof(policy->reserved); i++) {
        if (policy->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    /* Validate enum values */
    if (policy->unanchored_behavior > TOPOLOGY_UNANCHORED_FAIL_CLOSED) return SEMANTIC_E_INVAL;
    if (policy->capacity_overflow_behavior > TOPOLOGY_CAPACITY_OVERFLOW_FAIL_CLOSED) return SEMANTIC_E_INVAL;
    if (policy->conflict_policy > TOPOLOGY_CONFLICT_PRESERVE_BOTH) return SEMANTIC_E_INVAL;
    if (policy->transport_policy > TOPOLOGY_TRANSPORT_TRACE_ONLY) return SEMANTIC_E_INVAL;
    if (policy->metric_policy > TOPOLOGY_METRIC_LOCAL_ORDER_ONLY) return SEMANTIC_E_INVAL;

    /* Validate flags */
    if (policy->flags & ~TOPOLOGY_POLICY_FLAG_MASK) return SEMANTIC_E_RESERVATION;

    /* Limits must be non-zero */
    if (policy->max_vertices == 0) return SEMANTIC_E_INVAL;
    if (policy->max_incidences == 0) return SEMANTIC_E_INVAL;
    if (policy->max_anchors == 0) return SEMANTIC_E_INVAL;
    if (policy->max_constellations == 0) return SEMANTIC_E_INVAL;
    if (policy->max_affiliations_per_vertex == 0) return SEMANTIC_E_INVAL;
    if (policy->max_semantic_path_cost == 0) return SEMANTIC_E_INVAL;
    if (policy->max_semantic_path_hops == 0) return SEMANTIC_E_INVAL;
    if (policy->max_bridges == 0) return SEMANTIC_E_INVAL;
    if (policy->max_metric_hints == 0) return SEMANTIC_E_INVAL;

    return SEMANTIC_OK;
}

int elpis_topology_policy_check_capacity(
    const elpis_semantic_topology_policy_v1 *policy,
    uint32_t vertex_count, uint32_t incidence_count,
    uint32_t anchor_count, uint32_t constellation_count) {
    if (!policy) return SEMANTIC_E_INVAL;
    if (vertex_count > policy->max_vertices) return SEMANTIC_E_CARDINALITY;
    if (incidence_count > policy->max_incidences) return SEMANTIC_E_CARDINALITY;
    if (anchor_count > policy->max_anchors) return SEMANTIC_E_CARDINALITY;
    if (constellation_count > policy->max_constellations) return SEMANTIC_E_CARDINALITY;
    return SEMANTIC_OK;
}

int elpis_write_topology_policy(const char *path,
                                 const elpis_semantic_topology_policy_v1 *policy) {
    if (!path || !policy) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, policy, sizeof(*policy));
    if ((size_t)w != sizeof(*policy)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}

int elpis_read_topology_policy(const char *path,
                                elpis_semantic_topology_policy_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    if ((size_t)r != sizeof(*out)) { close(fd); return SEMANTIC_E_IO; }
    close(fd);
    return elpis_topology_policy_validate(out);
}
