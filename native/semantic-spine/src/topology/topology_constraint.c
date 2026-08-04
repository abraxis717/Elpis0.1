/* topology_constraint.c — Placement constraint generation for P7. */
#include "elpis_semantic/topology_constraint.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>

void elpis_topology_constraints_init(
    elpis_semantic_topology_constraints_v1 *constraints) {
    if (!constraints) return;
    memset(constraints, 0, sizeof(*constraints));
    constraints->abi_version = TOPOLOGY_CONSTRAINT_ABI_VERSION;
}

int elpis_topology_generate_constraints(
    elpis_semantic_topology_constraints_v1 *constraints,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_anchors_v1 *anchors,
    const elpis_semantic_topology_constellations_v1 *constellations,
    const elpis_semantic_topology_roles_v1 *roles,
    const elpis_semantic_topology_conflicts_v1 *conflicts,
    const elpis_semantic_topology_bridges_v1 *bridges,
    const elpis_semantic_topology_metric_hints_v1 *hints,
    const elpis_semantic_topology_addresses_v1 *addresses) {
    (void)policy;
    if (!constraints || !graph || !anchors || !constellations ||
        !roles || !conflicts || !bridges || !hints || !addresses)
        return SEMANTIC_E_INVAL;

    uint32_t idx = 0;

    /* ANCHOR_VERTEX constraints — one per anchor */
    for (uint32_t a = 0; a < anchors->anchor_count && idx < TOPOLOGY_MAX_CONSTRAINT_COUNT; a++) {
        topology_constraint_v1 *c = &constraints->constraints[idx++];
        memset(c, 0, sizeof(*c));
        c->abi_version = TOPOLOGY_CONSTRAINT_ABI_VERSION;
        c->constraint_type = TOPOLOGY_CONSTRAINT_ANCHOR_VERTEX;
        c->mandatory_flag = 1;
        memcpy(&c->field_digests[0], &anchors->anchors[a].anchor_vertex_digest, HACF_DIGEST_BYTES);
        c->field_count = 1;
    }

    /* CONSTELLATION_MEMBERSHIP constraints — one per constellation */
    for (uint32_t cs = 0; cs < constellations->constellation_count && idx < TOPOLOGY_MAX_CONSTRAINT_COUNT; cs++) {
        const topology_constellation_v1 *con = &constellations->constellations[cs];
        topology_constraint_v1 *c = &constraints->constraints[idx++];
        memset(c, 0, sizeof(*c));
        c->abi_version = TOPOLOGY_CONSTRAINT_ABI_VERSION;
        c->constraint_type = TOPOLOGY_CONSTRAINT_CONSTELLATION_MEMBERSHIP;
        c->mandatory_flag = 1;
        memcpy(&c->field_digests[0], &con->anchor_digest, HACF_DIGEST_BYTES);
        c->field_count = 1;
    }

    /* LANE_MEMBERSHIP constraints — one per role assignment */
    for (uint32_t r = 0; r < roles->assignment_count && idx < TOPOLOGY_MAX_CONSTRAINT_COUNT; r++) {
        topology_constraint_v1 *c = &constraints->constraints[idx++];
        memset(c, 0, sizeof(*c));
        c->abi_version = TOPOLOGY_CONSTRAINT_ABI_VERSION;
        c->constraint_type = TOPOLOGY_CONSTRAINT_LANE_MEMBERSHIP;
        c->mandatory_flag = 1;
        memcpy(&c->field_digests[0], &roles->assignments[r].vertex_digest, HACF_DIGEST_BYTES);
        c->field_count = 1;
    }

    /* CONFLICT_SHARED_TARGET and CONFLICT_POLARITY_SEPARATION */
    for (uint32_t cf = 0; cf < conflicts->conflict_count && idx < TOPOLOGY_MAX_CONSTRAINT_COUNT; cf++) {
        topology_constraint_v1 *c = &constraints->constraints[idx++];
        memset(c, 0, sizeof(*c));
        c->abi_version = TOPOLOGY_CONSTRAINT_ABI_VERSION;
        c->constraint_type = TOPOLOGY_CONSTRAINT_CONFLICT_SHARED_TARGET;
        c->mandatory_flag = 1;
        memcpy(&c->field_digests[0], &conflicts->conflicts[cf].conflict_target_vertex, HACF_DIGEST_BYTES);
        c->field_count = 1;

        /* Polarity separation constraint */
        if (idx < TOPOLOGY_MAX_CONSTRAINT_COUNT) {
            topology_constraint_v1 *c2 = &constraints->constraints[idx++];
            memset(c2, 0, sizeof(*c2));
            c2->abi_version = TOPOLOGY_CONSTRAINT_ABI_VERSION;
            c2->constraint_type = TOPOLOGY_CONSTRAINT_CONFLICT_POLARITY_SEPARATION;
            c2->mandatory_flag = 1;
            memcpy(&c2->field_digests[0], &conflicts->conflicts[cf].conflict_target_vertex, HACF_DIGEST_BYTES);
            c2->field_count = 1;
        }
    }

    /* BRIDGE_MEMBERSHIP constraints */
    for (uint32_t br = 0; br < bridges->bridge_count && idx < TOPOLOGY_MAX_CONSTRAINT_COUNT; br++) {
        topology_constraint_v1 *c = &constraints->constraints[idx++];
        memset(c, 0, sizeof(*c));
        c->abi_version = TOPOLOGY_CONSTRAINT_ABI_VERSION;
        c->constraint_type = TOPOLOGY_CONSTRAINT_BRIDGE_MEMBERSHIP;
        c->mandatory_flag = 1;
        memcpy(&c->field_digests[0], &bridges->bridges[br].source_vertex_digest, HACF_DIGEST_BYTES);
        c->field_count = 1;
    }

    /* METRIC_LOCAL_ORDER_HINT constraints — non-mandatory */
    for (uint32_t m = 0; m < hints->hint_count && idx < TOPOLOGY_MAX_CONSTRAINT_COUNT; m++) {
        topology_constraint_v1 *c = &constraints->constraints[idx++];
        memset(c, 0, sizeof(*c));
        c->abi_version = TOPOLOGY_CONSTRAINT_ABI_VERSION;
        c->constraint_type = TOPOLOGY_CONSTRAINT_METRIC_LOCAL_ORDER_HINT;
        c->mandatory_flag = 0;
        memcpy(&c->field_digests[0], &hints->hints[m].source_vertex_digest, HACF_DIGEST_BYTES);
        memcpy(&c->field_digests[1], &hints->hints[m].neighbor_vertex_digest, HACF_DIGEST_BYTES);
        c->field_count = 2;
    }

    constraints->constraint_count = idx;

    /* Compute constraint plane digest */
    elpis_topology_constraint_plane_digest(constraints, &constraints->constraint_plane_digest);

    return SEMANTIC_OK;
}

int elpis_topology_constraint_plane_digest(
    const elpis_semantic_topology_constraints_v1 *constraints, hacf_digest *out) {
    if (!constraints || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology.constraint_plane.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&constraints->constraint_count,
                       sizeof(constraints->constraint_count));

    for (uint32_t i = 0; i < constraints->constraint_count; i++) {
        const topology_constraint_v1 *c = &constraints->constraints[i];
        elpis_sha256_update(&ctx, (const uint8_t *)&c->constraint_type, sizeof(c->constraint_type));
        elpis_sha256_update(&ctx, (const uint8_t *)&c->mandatory_flag, sizeof(c->mandatory_flag));
        elpis_sha256_update(&ctx, (const uint8_t *)&c->field_count, sizeof(c->field_count));
        for (uint32_t f = 0; f < c->field_count; f++) {
            elpis_sha256_update(&ctx, c->field_digests[f].bytes, HACF_DIGEST_BYTES);
        }
    }

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_constraints_validate(
    const elpis_semantic_topology_constraints_v1 *constraints) {
    if (!constraints) return SEMANTIC_E_INVAL;
    if (constraints->abi_version != TOPOLOGY_CONSTRAINT_ABI_VERSION) return SEMANTIC_E_INVAL;

    for (size_t i = 0; i < sizeof(constraints->reserved); i++) {
        if (constraints->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    for (uint32_t i = 0; i < constraints->constraint_count; i++) {
        const topology_constraint_v1 *c = &constraints->constraints[i];
        if (c->abi_version != TOPOLOGY_CONSTRAINT_ABI_VERSION) return SEMANTIC_E_INVAL;
        if (c->constraint_type > TOPOLOGY_CONSTRAINT_PROVENANCE_TRACE_DEPENDENCY)
            return SEMANTIC_E_INVAL;
        if (c->mandatory_flag > 1) return SEMANTIC_E_INVAL;
        if (c->field_count > TOPOLOGY_MAX_CONSTRAINT_FIELDS) return SEMANTIC_E_INVAL;
        for (size_t j = 0; j < sizeof(c->reserved); j++) {
            if (c->reserved[j] != 0) return SEMANTIC_E_RESERVATION;
        }
    }
    return SEMANTIC_OK;
}

int elpis_write_topology_constraints(const char *path,
    const elpis_semantic_topology_constraints_v1 *constraints) {
    if (!path || !constraints) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, constraints, sizeof(*constraints));
    if ((size_t)w != sizeof(*constraints)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}

int elpis_read_topology_constraints(const char *path,
    elpis_semantic_topology_constraints_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    if ((size_t)r != sizeof(*out)) { close(fd); return SEMANTIC_E_IO; }
    close(fd);
    return elpis_topology_constraints_validate(out);
}
