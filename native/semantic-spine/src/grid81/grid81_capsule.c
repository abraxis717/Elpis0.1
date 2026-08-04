/* grid81_capsule.c — Topology capsule v1. */
#include "elpis_semantic/grid81_capsule.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <unistd.h>
#include <fcntl.h>
#include <string.h>

int elpis_grid81_capsule_key_cmp(
    const grid81_capsule_key_v1 *a, const grid81_capsule_key_v1 *b) {
    if (!a || !b) return SEMANTIC_E_INVAL;
    if (a->primary_constellation_index != b->primary_constellation_index) return 1;
    if (a->semantic_stratum != b->semantic_stratum) return 1;
    if (a->primary_lane != b->primary_lane) return 1;
    if (a->primary_role != b->primary_role) return 1;
    if (a->relation_family_class != b->relation_family_class) return 1;
    if (memcmp(a->cluster_key_digest.bytes, b->cluster_key_digest.bytes, HACF_DIGEST_BYTES) != 0) return 1;
    if (a->mandatory_flag != b->mandatory_flag) return 1;
    if (a->conflict_branch_class != b->conflict_branch_class) return 1;
    if (a->bridge_membership != b->bridge_membership) return 1;
    return 0;
}

int elpis_grid81_capsule_key_cmp_order(
    const grid81_capsule_key_v1 *a, const grid81_capsule_key_v1 *b) {
    if (!a || !b) return SEMANTIC_E_INVAL;
    if (a->primary_constellation_index < b->primary_constellation_index) return -1;
    if (a->primary_constellation_index > b->primary_constellation_index) return 1;
    if (a->semantic_stratum < b->semantic_stratum) return -1;
    if (a->semantic_stratum > b->semantic_stratum) return 1;
    if (a->primary_lane < b->primary_lane) return -1;
    if (a->primary_lane > b->primary_lane) return 1;
    if (a->primary_role < b->primary_role) return -1;
    if (a->primary_role > b->primary_role) return 1;
    if (a->relation_family_class < b->relation_family_class) return -1;
    if (a->relation_family_class > b->relation_family_class) return 1;
    int c = memcmp(a->cluster_key_digest.bytes, b->cluster_key_digest.bytes, HACF_DIGEST_BYTES);
    if (c != 0) return c;
    if (a->mandatory_flag < b->mandatory_flag) return -1;
    if (a->mandatory_flag > b->mandatory_flag) return 1;
    if (a->conflict_branch_class < b->conflict_branch_class) return -1;
    if (a->conflict_branch_class > b->conflict_branch_class) return 1;
    if (a->bridge_membership < b->bridge_membership) return -1;
    if (a->bridge_membership > b->bridge_membership) return 1;
    return 0;
}

void elpis_grid81_capsule_init(elpis_semantic_grid81_capsule_v1 *capsule) {
    if (!capsule) return;
    memset(capsule, 0, sizeof(*capsule));
    capsule->abi_version = GRID81_CAPSULE_ABI_VERSION;
}

void elpis_grid81_capsule_manifest_init(
    elpis_semantic_grid81_capsule_manifest_v1 *manifest) {
    if (!manifest) return;
    memset(manifest, 0, sizeof(*manifest));
    manifest->abi_version = GRID81_CAPSULE_ABI_VERSION;
}

int elpis_grid81_capsule_identity(
    const elpis_semantic_grid81_capsule_v1 *capsule, hacf_digest *out) {
    if (!capsule || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.grid81_capsule.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f;
    f = capsule->abi_version;                    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, capsule->P6_topology_IR_digest.bytes, 32);
    elpis_sha256_update(&ctx, capsule->P6_topology_handoff_digest.bytes, 32);
    f = capsule->primary_constellation_index;    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, capsule->primary_constellation_digest.bytes, 32);
    elpis_sha256_update(&ctx, capsule->primary_anchor_digest.bytes, 32);
    f = capsule->semantic_stratum;               elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = capsule->primary_lane;                   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = capsule->primary_role;                   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = capsule->relation_family_class;          elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_update(&ctx, capsule->cluster_key_digest.bytes, 32);
    f = capsule->mandatory_capsule;              elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = capsule->conflict_membership;            elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = capsule->bridge_membership;              elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = capsule->scope_membership;               elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = capsule->qualifier_membership;           elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = capsule->metric_only;                    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = capsule->vertex_count;                   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < capsule->vertex_count; i++) {
        elpis_sha256_update(&ctx, capsule->ordered_topology_vertex_digests[i].bytes, 32);
    }
    f = capsule->address_count;                  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < capsule->address_count; i++) {
        elpis_sha256_update(&ctx, capsule->ordered_topology_address_digests[i].bytes, 32);
    }
    f = capsule->affiliation_count;              elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = capsule->constraint_count;               elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_grid81_capsule_validate(
    const elpis_semantic_grid81_capsule_v1 *capsule) {
    if (!capsule) return SEMANTIC_E_INVAL;
    if (capsule->abi_version != GRID81_CAPSULE_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (capsule->vertex_count > GRID81_MAX_VERTICES_PER_CAPSULE) return SEMANTIC_E_INVAL;
    if (capsule->address_count > GRID81_MAX_ADDRESSES_PER_CAPSULE) return SEMANTIC_E_INVAL;
    if (capsule->affiliation_count > GRID81_MAX_AFFILIATIONS_PER_CAPSULE) return SEMANTIC_E_INVAL;
    if (capsule->constraint_count > GRID81_MAX_CONSTRAINTS_PER_CAPSULE) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(capsule->reserved); i++) {
        if (capsule->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_grid81_capsule_manifest_identity(
    const elpis_semantic_grid81_capsule_manifest_v1 *manifest, hacf_digest *out) {
    if (!manifest || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.grid81_capsule_manifest.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    uint32_t f = manifest->abi_version; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = manifest->capsule_count;        elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < manifest->capsule_count; i++) {
        hacf_digest d;
        elpis_grid81_capsule_identity(&manifest->capsules[i], &d);
        elpis_sha256_update(&ctx, d.bytes, 32);
    }
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_write_grid81_capsule_manifest(const char *path,
    const elpis_semantic_grid81_capsule_manifest_v1 *manifest) {
    if (!path || !manifest) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, manifest, sizeof(*manifest));
    if ((size_t)w != sizeof(*manifest)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd); close(fd);
    return SEMANTIC_OK;
}

int elpis_read_grid81_capsule_manifest(const char *path,
    elpis_semantic_grid81_capsule_manifest_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    close(fd);
    if ((size_t)r != sizeof(*out)) return SEMANTIC_E_IO;
    return SEMANTIC_OK;
}
