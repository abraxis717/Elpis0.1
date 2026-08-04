/* topology_address.c — Abstract topology address assignment. */
#include "elpis_semantic/topology_address.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>

void elpis_topology_addresses_init(elpis_semantic_topology_addresses_v1 *addrs) {
    if (!addrs) return;
    memset(addrs, 0, sizeof(*addrs));
    addrs->abi_version = TOPOLOGY_ADDRESS_ABI_VERSION;
}

int elpis_topology_address_identity(
    const topology_address_v1 *a, hacf_digest *out) {
    if (!a || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology_address.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&a->abi_version, sizeof(a->abi_version));
    elpis_sha256_update(&ctx, a->vertex_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&a->constellation_index, sizeof(a->constellation_index));
    elpis_sha256_update(&ctx, (const uint8_t *)&a->semantic_stratum, sizeof(a->semantic_stratum));
    elpis_sha256_update(&ctx, (const uint8_t *)&a->primary_lane, sizeof(a->primary_lane));
    elpis_sha256_update(&ctx, (const uint8_t *)&a->primary_role, sizeof(a->primary_role));
    elpis_sha256_update(&ctx, (const uint8_t *)&a->relation_family_class, sizeof(a->relation_family_class));
    elpis_sha256_update(&ctx, a->cluster_key_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&a->local_ordinal, sizeof(a->local_ordinal));
    elpis_sha256_update(&ctx, (const uint8_t *)&a->flags, sizeof(a->flags));
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_assign_addresses(
    elpis_semantic_topology_addresses_v1 *addrs,
    const elpis_semantic_topology_policy_v1 *policy,
    const elpis_semantic_topology_graph_v1 *graph,
    const elpis_semantic_topology_constellations_v1 *constellations,
    const elpis_semantic_topology_roles_v1 *roles,
    const elpis_semantic_topology_metric_hints_v1 *hints) {
    (void)hints;
    if (!addrs || !policy || !graph || !constellations || !roles) return SEMANTIC_E_INVAL;

    /* Build cluster-key buckets and assign local ordinals */
    /* Cluster key = constellation + stratum + lane + role + relation_family */
    typedef struct {
        uint32_t constellation_index;
        uint32_t stratum;
        uint32_t lane;
        uint32_t role;
        uint32_t relation_family;
        hacf_digest key_digest;
        uint32_t ordinal_counter;
    } bucket_t;

    bucket_t buckets[TOPOLOGY_DEFAULT_MAX_VERTICES];
    uint32_t bucket_count = 0;
    memset(buckets, 0, sizeof(buckets));

    uint32_t addr_idx = 0;
    for (uint32_t v = 0; v < graph->vertex_count; v++) {
        const topology_vertex_v1 *vert = &graph->vertices[v];

        /* Find role assignment */
        const topology_role_assignment_v1 *ra = NULL;
        for (uint32_t r = 0; r < roles->assignment_count; r++) {
            if (hacf_digest_cmp(&roles->assignments[r].vertex_digest,
                                 &vert->vertex_identity) == 0) {
                ra = &roles->assignments[r];
                break;
            }
        }
        if (!ra) continue;

        /* Find constellation */
        int constellation_idx = elpis_topology_find_constellation(constellations, &vert->vertex_identity);
        uint32_t constellation_index = (constellation_idx >= 0) ? (uint32_t)constellation_idx : 0xFFFFFFFF;

        /* Determine relation family from incidences */
        uint32_t relation_family = TOPOLOGY_CLASS_CONTEXT;
        for (uint32_t i = 0; i < graph->incidence_count; i++) {
            if (hacf_digest_cmp(&graph->incidences[i].node_vertex_digest,
                                 &vert->vertex_identity) == 0) {
                relation_family = graph->incidences[i].relation_class;
                break;
            }
        }

        /* Find or create bucket */
        uint32_t bucket_idx = bucket_count;
        for (uint32_t b = 0; b < bucket_count; b++) {
            if (buckets[b].constellation_index == constellation_index &&
                buckets[b].stratum == ra->stratum &&
                buckets[b].lane == ra->lane &&
                buckets[b].role == ra->primary_role &&
                buckets[b].relation_family == relation_family) {
                bucket_idx = b;
                break;
            }
        }

        if (bucket_idx == bucket_count) {
            /* New bucket */
            buckets[bucket_count].constellation_index = constellation_index;
            buckets[bucket_count].stratum = ra->stratum;
            buckets[bucket_count].lane = ra->lane;
            buckets[bucket_count].role = ra->primary_role;
            buckets[bucket_count].relation_family = relation_family;
            buckets[bucket_count].ordinal_counter = 0;

            /* Compute cluster key digest */
            const char domain[] = "elpis.semantic.topology.cluster_key.v1";
            hacf_digest domain_tag;
            elpis_sha256(domain, strlen(domain), domain_tag.bytes);
            elpis_sha256_ctx ctx;
            elpis_sha256_init(&ctx);
            elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
            elpis_sha256_update(&ctx, (const uint8_t *)&constellation_index, sizeof(constellation_index));
            elpis_sha256_update(&ctx, (const uint8_t *)&ra->stratum, sizeof(ra->stratum));
            elpis_sha256_update(&ctx, (const uint8_t *)&ra->lane, sizeof(ra->lane));
            elpis_sha256_update(&ctx, (const uint8_t *)&ra->primary_role, sizeof(ra->primary_role));
            elpis_sha256_update(&ctx, (const uint8_t *)&relation_family, sizeof(relation_family));
            elpis_sha256_final(&ctx, buckets[bucket_count].key_digest.bytes);
            bucket_count++;
        }

        /* Create address */
        topology_address_v1 *addr = &addrs->addresses[addr_idx++];
        memset(addr, 0, sizeof(*addr));
        addr->abi_version = TOPOLOGY_ADDRESS_ABI_VERSION;
        memcpy(&addr->vertex_digest, &vert->vertex_identity, HACF_DIGEST_BYTES);
        addr->constellation_index = constellation_index;
        addr->semantic_stratum = ra->stratum;
        addr->primary_lane = ra->lane;
        addr->primary_role = ra->primary_role;
        addr->relation_family_class = relation_family;
        memcpy(&addr->cluster_key_digest, &buckets[bucket_idx].key_digest, HACF_DIGEST_BYTES);
        addr->local_ordinal = buckets[bucket_idx].ordinal_counter++;

        hacf_digest id;
        elpis_topology_address_identity(addr, &id);
        memcpy(addr->address_identity.bytes, id.bytes, HACF_DIGEST_BYTES);
    }

    addrs->address_count = addr_idx;

    /* Compute address plane digest */
    elpis_topology_address_plane_digest(addrs, &addrs->address_plane_digest);

    return SEMANTIC_OK;
}

int elpis_topology_address_plane_digest(
    const elpis_semantic_topology_addresses_v1 *addrs, hacf_digest *out) {
    if (!addrs || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology.address_plane.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&addrs->address_count, sizeof(addrs->address_count));

    for (uint32_t i = 0; i < addrs->address_count; i++) {
        elpis_sha256_update(&ctx, addrs->addresses[i].address_identity.bytes, HACF_DIGEST_BYTES);
    }

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_addresses_validate(
    const elpis_semantic_topology_addresses_v1 *addrs) {
    if (!addrs) return SEMANTIC_E_INVAL;
    if (addrs->abi_version != TOPOLOGY_ADDRESS_ABI_VERSION) return SEMANTIC_E_INVAL;

    for (size_t i = 0; i < sizeof(addrs->reserved); i++) {
        if (addrs->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    for (uint32_t i = 0; i < addrs->address_count; i++) {
        const topology_address_v1 *a = &addrs->addresses[i];
        if (a->abi_version != TOPOLOGY_ADDRESS_ABI_VERSION) return SEMANTIC_E_INVAL;
        if (a->primary_lane > TOPOLOGY_LANE_NEUTRAL) return SEMANTIC_E_INVAL;
        if (a->primary_role > TOPOLOGY_ROLE_NEUTRAL) return SEMANTIC_E_INVAL;
        for (size_t j = 0; j < sizeof(a->reserved); j++) {
            if (a->reserved[j] != 0) return SEMANTIC_E_RESERVATION;
        }
    }

    /* Every vertex should have exactly one address */
    /* (verified by caller; structural check here) */
    return SEMANTIC_OK;
}

int elpis_write_topology_addresses(const char *path,
    const elpis_semantic_topology_addresses_v1 *addrs) {
    if (!path || !addrs) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, addrs, sizeof(*addrs));
    if ((size_t)w != sizeof(*addrs)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}
