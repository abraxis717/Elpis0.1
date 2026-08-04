/* topology_constellation.c — Constellations and affiliations. */
#include "elpis_semantic/topology_constellation.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>

void elpis_topology_constellations_init(
    elpis_semantic_topology_constellations_v1 *constellations) {
    if (!constellations) return;
    memset(constellations, 0, sizeof(*constellations));
    constellations->abi_version = TOPOLOGY_CONSTELLATION_ABI_VERSION;
}

int elpis_topology_constellation_identity(
    const topology_constellation_v1 *c, hacf_digest *out) {
    if (!c || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology_constellation.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&c->abi_version, sizeof(c->abi_version));
    elpis_sha256_update(&ctx, c->anchor_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, c->anchor_vertex_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&c->primary_member_count, sizeof(c->primary_member_count));
    for (uint32_t i = 0; i < c->primary_member_count; i++) {
        elpis_sha256_update(&ctx, c->primary_members[i].bytes, HACF_DIGEST_BYTES);
    }
    elpis_sha256_update(&ctx, (const uint8_t *)&c->secondary_member_count, sizeof(c->secondary_member_count));
    for (uint32_t i = 0; i < c->secondary_member_count; i++) {
        elpis_sha256_update(&ctx, c->secondary_members[i].bytes, HACF_DIGEST_BYTES);
    }
    elpis_sha256_update(&ctx, (const uint8_t *)&c->bridge_member_count, sizeof(c->bridge_member_count));
    for (uint32_t i = 0; i < c->bridge_member_count; i++) {
        elpis_sha256_update(&ctx, c->bridge_members[i].bytes, HACF_DIGEST_BYTES);
    }
    elpis_sha256_update(&ctx, (const uint8_t *)&c->min_stratum, sizeof(c->min_stratum));
    elpis_sha256_update(&ctx, (const uint8_t *)&c->max_stratum, sizeof(c->max_stratum));
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_construct_constellations(
    elpis_semantic_topology_constellations_v1 *constellations,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_anchors_v1 *anchors) {
    (void)graph;
    if (!constellations || !policy || !anchors) return SEMANTIC_E_INVAL;

    /* One constellation per anchor */
    uint32_t affiliation_idx = 0;

    for (uint32_t a = 0; a < anchors->anchor_count; a++) {
        const topology_anchor_v1 *anchor = &anchors->anchors[a];
        hacf_digest anchor_id;
        elpis_topology_anchor_identity(anchor, &anchor_id);

        topology_constellation_v1 *c = &constellations->constellations[constellations->constellation_count];
        memset(c, 0, sizeof(*c));
        c->abi_version = TOPOLOGY_CONSTELLATION_ABI_VERSION;
        memcpy(&c->anchor_digest, &anchor_id, HACF_DIGEST_BYTES);
        memcpy(&c->anchor_vertex_digest, &anchor->anchor_vertex_digest, HACF_DIGEST_BYTES);

        /* Find distance records for this anchor */
        uint32_t best_cost = UINT32_MAX;

        /* Scan distance records to find primary and secondary members */
        for (uint32_t d = 0; d < constellations->distance_record_count; d++) {
            const topology_distance_record_v1 *rec = &constellations->distance_records[d];
            if (hacf_digest_cmp(&rec->anchor_digest, &anchor_id) != 0) continue;

            /* Track best cost */
            if (rec->semantic_cost < best_cost) best_cost = rec->semantic_cost;
        }

        /* Assign primary members (equal-best lowest cost) */
        for (uint32_t d = 0; d < constellations->distance_record_count; d++) {
            const topology_distance_record_v1 *rec = &constellations->distance_records[d];
            if (hacf_digest_cmp(&rec->anchor_digest, &anchor_id) != 0) continue;

            if (rec->semantic_cost == best_cost) {
                /* Primary member */
                if (c->primary_member_count < TOPOLOGY_DEFAULT_MAX_VERTICES) {
                    memcpy(&c->primary_members[c->primary_member_count],
                           &rec->target_vertex_digest, HACF_DIGEST_BYTES);
                    c->primary_member_count++;

                    /* Add affiliation */
                    if (affiliation_idx < TOPOLOGY_DEFAULT_MAX_VERTICES * TOPOLOGY_DEFAULT_MAX_AFFILIATIONS) {
                        topology_affiliation_v1 *aff = &constellations->affiliations[affiliation_idx++];
                        memset(aff, 0, sizeof(*aff));
                        memcpy(&aff->vertex_digest, &rec->target_vertex_digest, HACF_DIGEST_BYTES);
                        memcpy(&aff->anchor_digest, &anchor_id, HACF_DIGEST_BYTES);
                        aff->affiliation_kind = TOPOLOGY_AFFILIATION_PRIMARY;
                        aff->semantic_cost = rec->semantic_cost;
                        aff->hop_count = rec->hop_count;
                    }
                }
            }
        }

        /* Stratum = best cost as integer stratum */
        c->min_stratum = best_cost;
        c->max_stratum = best_cost;

        /* Compute identity */
        hacf_digest id;
        elpis_topology_constellation_identity(c, &id);
        memcpy(c->constellation_identity.bytes, id.bytes, HACF_DIGEST_BYTES);

        constellations->constellation_count++;
    }

    constellations->affiliation_count = affiliation_idx;

    /* Compute constellation plane digest */
    elpis_topology_constellation_plane_digest(constellations, &constellations->constellation_plane_digest);

    return SEMANTIC_OK;
}

int elpis_topology_constellation_plane_digest(
    const elpis_semantic_topology_constellations_v1 *constellations, hacf_digest *out) {
    if (!constellations || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology.constellation_plane.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&constellations->constellation_count,
                       sizeof(constellations->constellation_count));

    for (uint32_t i = 0; i < constellations->constellation_count; i++) {
        elpis_sha256_update(&ctx, constellations->constellations[i].constellation_identity.bytes,
                           HACF_DIGEST_BYTES);
    }

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_constellations_validate(
    const elpis_semantic_topology_constellations_v1 *constellations) {
    if (!constellations) return SEMANTIC_E_INVAL;
    if (constellations->abi_version != TOPOLOGY_CONSTELLATION_ABI_VERSION) return SEMANTIC_E_INVAL;

    /* Check reserved */
    for (size_t i = 0; i < sizeof(constellations->reserved); i++) {
        if (constellations->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    for (uint32_t i = 0; i < constellations->constellation_count; i++) {
        const topology_constellation_v1 *c = &constellations->constellations[i];
        if (c->abi_version != TOPOLOGY_CONSTELLATION_ABI_VERSION) return SEMANTIC_E_INVAL;
        if (c->min_stratum > c->max_stratum) return SEMANTIC_E_INVAL;
        for (size_t j = 0; j < sizeof(c->reserved); j++) {
            if (c->reserved[j] != 0) return SEMANTIC_E_RESERVATION;
        }
    }

    return SEMANTIC_OK;
}

int elpis_topology_find_constellation(
    const elpis_semantic_topology_constellations_v1 *constellations,
    const hacf_digest *vertex_digest) {
    if (!constellations || !vertex_digest) return -1;
    for (uint32_t c = 0; c < constellations->constellation_count; c++) {
        for (uint32_t m = 0; m < constellations->constellations[c].primary_member_count; m++) {
            if (hacf_digest_cmp(&constellations->constellations[c].primary_members[m],
                                 vertex_digest) == 0) {
                return (int)c;
            }
        }
    }
    return -1;
}

int elpis_write_topology_constellations(const char *path,
    const elpis_semantic_topology_constellations_v1 *constellations) {
    if (!path || !constellations) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, constellations, sizeof(*constellations));
    if ((size_t)w != sizeof(*constellations)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}

int elpis_read_topology_constellations(const char *path,
    elpis_semantic_topology_constellations_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    if ((size_t)r != sizeof(*out)) { close(fd); return SEMANTIC_E_IO; }
    close(fd);
    return elpis_topology_constellations_validate(out);
}
