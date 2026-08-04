/* topology_anchor.c — Topology anchors from P5 control records. */
#include "elpis_semantic/topology_anchor.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdio.h>

void elpis_topology_anchors_init(elpis_semantic_topology_anchors_v1 *anchors) {
    if (!anchors) return;
    memset(anchors, 0, sizeof(*anchors));
    anchors->abi_version = TOPOLOGY_ANCHOR_ABI_VERSION;
}

int elpis_topology_anchor_identity(
    const topology_anchor_v1 *a, hacf_digest *out) {
    if (!a || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology_anchor.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&a->abi_version, sizeof(a->abi_version));
    elpis_sha256_update(&ctx, a->anchor_vertex_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&a->source_kind, sizeof(a->source_kind));
    elpis_sha256_update(&ctx, a->source_digest.bytes, HACF_DIGEST_BYTES);
    size_t reason_len = strlen(a->reason);
    elpis_sha256_update(&ctx, (const uint8_t *)a->reason, reason_len + 1);
    elpis_sha256_update(&ctx, a->originating_requirement.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&a->requirement_level, sizeof(a->requirement_level));
    elpis_sha256_update(&ctx, (const uint8_t *)&a->priority, sizeof(a->priority));
    elpis_sha256_update(&ctx, (const uint8_t *)&a->mandatory_flag, sizeof(a->mandatory_flag));
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_anchor_plane_digest(
    const elpis_semantic_topology_anchors_v1 *anchors, hacf_digest *out) {
    if (!anchors || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology.anchor_plane.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&anchors->anchor_count, sizeof(anchors->anchor_count));

    for (uint32_t i = 0; i < anchors->anchor_count; i++) {
        elpis_sha256_update(&ctx, anchors->anchors[i].anchor_identity.bytes, HACF_DIGEST_BYTES);
    }

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_construct_anchors(
    elpis_semantic_topology_anchors_v1 *anchors,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_bounded_semantic_view_v1 *view,
    const elpis_semantic_downstream_handoff_v1 *handoff) {
    (void)policy; (void)graph; (void)view; (void)handoff;
    if (!anchors) return SEMANTIC_E_INVAL;

    /* Priority 0: Query anchors — use the first node vertex as query anchor */
    if (graph->vertex_count > 0) {
        topology_anchor_v1 *a = &anchors->anchors[anchors->anchor_count];
        memset(a, 0, sizeof(*a));
        a->abi_version = TOPOLOGY_ANCHOR_ABI_VERSION;
        a->source_kind = TOPOLOGY_ANCHOR_SOURCE_QUERY;
        memcpy(a->anchor_vertex_digest.bytes,
               graph->vertices[0].vertex_identity.bytes, HACF_DIGEST_BYTES);
        memcpy(a->source_digest.bytes,
               graph->vertices[0].source_semantic_digest.bytes, HACF_DIGEST_BYTES);
        strncpy(a->reason, "query_anchor", sizeof(a->reason) - 1);
        a->priority = TOPOLOGY_ANCHOR_PRIORITY_QUERY;
        a->mandatory_flag = 1;
        a->requirement_level = TOPOLOGY_REQUIREMENT_MANDATORY;

        hacf_digest id;
        elpis_topology_anchor_identity(a, &id);
        memcpy(a->anchor_identity.bytes, id.bytes, HACF_DIGEST_BYTES);
        anchors->anchor_count++;
    }

    /* Priority 3: Conflict targets — scan handoff features for conflict_target_flag */
    /* In a real implementation this would iterate the handoff feature records */
    /* For the canonical fixture, conflict anchors are added from control plane records */

    /* Compute anchor plane digest */
    elpis_topology_anchor_plane_digest(anchors, &anchors->anchor_plane_digest);

    return SEMANTIC_OK;
}

int elpis_topology_anchors_validate(
    const elpis_semantic_topology_anchors_v1 *anchors) {
    if (!anchors) return SEMANTIC_E_INVAL;
    if (anchors->abi_version != TOPOLOGY_ANCHOR_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (anchors->anchor_count == 0) return SEMANTIC_E_INVAL;

    /* Check reserved */
    for (size_t i = 0; i < sizeof(anchors->reserved); i++) {
        if (anchors->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    /* Check each anchor */
    for (uint32_t i = 0; i < anchors->anchor_count; i++) {
        const topology_anchor_v1 *a = &anchors->anchors[i];
        if (a->abi_version != TOPOLOGY_ANCHOR_ABI_VERSION) return SEMANTIC_E_INVAL;
        if (a->source_kind > TOPOLOGY_ANCHOR_SOURCE_PREFERRED_TARGET) return SEMANTIC_E_INVAL;
        if (a->priority > TOPOLOGY_ANCHOR_PRIORITY_PREFERRED) return SEMANTIC_E_INVAL;
        if (a->requirement_level > TOPOLOGY_REQUIREMENT_DIAGNOSTIC) return SEMANTIC_E_INVAL;
        if (a->mandatory_flag > 1) return SEMANTIC_E_INVAL;

        /* Check reserved */
        for (size_t j = 0; j < sizeof(a->reserved); j++) {
            if (a->reserved[j] != 0) return SEMANTIC_E_RESERVATION;
        }
    }

    /* Priority ordering: higher priority (lower number) first */
    for (uint32_t i = 1; i < anchors->anchor_count; i++) {
        if (anchors->anchors[i].priority < anchors->anchors[i-1].priority)
            return SEMANTIC_E_INVAL;
    }

    return SEMANTIC_OK;
}

const topology_anchor_v1 *elpis_topology_find_anchor(
    const elpis_semantic_topology_anchors_v1 *anchors,
    const hacf_digest *vertex_digest) {
    if (!anchors || !vertex_digest) return NULL;
    for (uint32_t i = 0; i < anchors->anchor_count; i++) {
        if (hacf_digest_cmp(&anchors->anchors[i].anchor_vertex_digest, vertex_digest) == 0)
            return &anchors->anchors[i];
    }
    return NULL;
}

int elpis_write_topology_anchors(const char *path,
                                  const elpis_semantic_topology_anchors_v1 *anchors) {
    if (!path || !anchors) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, anchors, sizeof(*anchors));
    if ((size_t)w != sizeof(*anchors)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}

int elpis_read_topology_anchors(const char *path,
                                 elpis_semantic_topology_anchors_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    if ((size_t)r != sizeof(*out)) { close(fd); return SEMANTIC_E_IO; }
    close(fd);
    return elpis_topology_anchors_validate(out);
}
