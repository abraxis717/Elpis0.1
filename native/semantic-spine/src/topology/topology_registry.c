/* elpis_semantic/topology_registry.c — Relation registry. */
#include "elpis_semantic/topology_registry.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>
#include <strings.h>

static const struct {
    const char *type_name;
    uint32_t topology_class;
    uint32_t traversal_cost;
    uint32_t lane;
    uint32_t polarity;
    uint32_t classification;
    uint32_t bridge_eligible;
} default_entries[] = {
    /* MENTIONS: class CONTEXT, cost 2, lane CONTEXT, neutral */
    {"MENTIONS", TOPOLOGY_CLASS_CONTEXT, 2, TOPOLOGY_LANE_CONTEXT, TOPOLOGY_POLARITY_NEUTRAL, TOPOLOGY_CLASSIFICATION_SEMANTIC, 0},
    /* DEFINES: class DEFINITION, cost 1, lane DEFINITION, neutral */
    {"DEFINES", TOPOLOGY_CLASS_DEFINITION, 1, TOPOLOGY_LANE_DEFINITION, TOPOLOGY_POLARITY_NEUTRAL, TOPOLOGY_CLASSIFICATION_SEMANTIC, 0},
    /* SUPPORTS: class SUPPORT, cost 1, lane SUPPORT, support polarity */
    {"SUPPORTS", TOPOLOGY_CLASS_SUPPORT, 1, TOPOLOGY_LANE_SUPPORT, TOPOLOGY_POLARITY_SUPPORT, TOPOLOGY_CLASSIFICATION_SEMANTIC, 0},
    /* CONTRADICTS: class CONTRADICTION, cost 1, lane CONTRADICTION, contradiction polarity */
    {"CONTRADICTS", TOPOLOGY_CLASS_CONTRADICTION, 1, TOPOLOGY_LANE_CONTRADICTION, TOPOLOGY_POLARITY_CONTRADICTION, TOPOLOGY_CLASSIFICATION_SEMANTIC, 0},
    /* QUALIFIES: class QUALIFICATION, cost 1, lane QUALIFIER */
    {"QUALIFIES", TOPOLOGY_CLASS_QUALIFIER, 1, TOPOLOGY_LANE_QUALIFIER, TOPOLOGY_POLARITY_NEUTRAL, TOPOLOGY_CLASSIFICATION_SEMANTIC, 0},
    /* LIMITS_SCOPE_OF: class SCOPE_LIMIT, cost 1, lane SCOPE */
    {"LIMITS_SCOPE_OF", TOPOLOGY_CLASS_SCOPE_LIMIT, 1, TOPOLOGY_LANE_SCOPE, TOPOLOGY_POLARITY_NEUTRAL, TOPOLOGY_CLASSIFICATION_SEMANTIC, 0},
    /* PROVIDES_CONTEXT_FOR: class CONTEXT, cost 2, lane CONTEXT */
    {"PROVIDES_CONTEXT_FOR", TOPOLOGY_CLASS_CONTEXT, 2, TOPOLOGY_LANE_CONTEXT, TOPOLOGY_POLARITY_NEUTRAL, TOPOLOGY_CLASSIFICATION_SEMANTIC, 0},
    /* Transport/provenance relations — TRACE_ONLY and nontraversable */
    {"RETRIEVED_FROM", TOPOLOGY_CLASS_TRACE_ONLY, 0, TOPOLOGY_LANE_NEUTRAL, TOPOLOGY_POLARITY_NEUTRAL, TOPOLOGY_CLASSIFICATION_TRANSPORT, 0},
    {"DERIVED_FROM_RETRIEVAL_BUNDLE", TOPOLOGY_CLASS_TRACE_ONLY, 0, TOPOLOGY_LANE_NEUTRAL, TOPOLOGY_POLARITY_NEUTRAL, TOPOLOGY_CLASSIFICATION_TRANSPORT, 0},
    {"RETRIEVAL_CONTEXT_EXPANSION", TOPOLOGY_CLASS_TRACE_ONLY, 0, TOPOLOGY_LANE_NEUTRAL, TOPOLOGY_POLARITY_NEUTRAL, TOPOLOGY_CLASSIFICATION_TRANSPORT, 0},
    {"EXTRACTED_FROM", TOPOLOGY_CLASS_TRACE_ONLY, 0, TOPOLOGY_LANE_NEUTRAL, TOPOLOGY_POLARITY_NEUTRAL, TOPOLOGY_CLASSIFICATION_TRANSPORT, 0},
    {"PROPOSED_BY", TOPOLOGY_CLASS_TRACE_ONLY, 0, TOPOLOGY_LANE_NEUTRAL, TOPOLOGY_POLARITY_NEUTRAL, TOPOLOGY_CLASSIFICATION_TRANSPORT, 0},
    {"ADMITTED_FROM_TYPING_BUNDLE", TOPOLOGY_CLASS_TRACE_ONLY, 0, TOPOLOGY_LANE_NEUTRAL, TOPOLOGY_POLARITY_NEUTRAL, TOPOLOGY_CLASSIFICATION_TRANSPORT, 0},
};

#define DEFAULT_ENTRY_COUNT (sizeof(default_entries) / sizeof(default_entries[0]))

void elpis_topology_registry_init(
    elpis_semantic_topology_relation_registry_v1 *registry) {
    if (!registry) return;
    memset(registry, 0, sizeof(*registry));
    registry->abi_version = TOPOLOGY_REGISTRY_ABI_VERSION;

    for (uint32_t i = 0; i < DEFAULT_ENTRY_COUNT; i++) {
        topology_relation_entry_v1 *e = &registry->entries[i];
        strncpy(e->semantic_relation_type, default_entries[i].type_name, sizeof(e->semantic_relation_type) - 1);
        e->semantic_relation_type[sizeof(e->semantic_relation_type) - 1] = '\0';
        /* numeric_relation_type assigned at compile time from type registry */
        e->numeric_relation_type = 0x20000000u + (i + 1);
        e->topology_class = default_entries[i].topology_class;
        e->traversal_cost = default_entries[i].traversal_cost;
        e->lane = default_entries[i].lane;
        e->polarity = default_entries[i].polarity;
        e->classification = default_entries[i].classification;
        e->bridge_eligible = default_entries[i].bridge_eligible;
    }
    registry->entry_count = (uint32_t)DEFAULT_ENTRY_COUNT;
}

int elpis_topology_registry_identity(
    const elpis_semantic_topology_relation_registry_v1 *registry, hacf_digest *out) {
    if (!registry || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology_relation_registry.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&registry->abi_version, sizeof(registry->abi_version));
    elpis_sha256_update(&ctx, (const uint8_t *)&registry->entry_count, sizeof(registry->entry_count));

    for (uint32_t i = 0; i < registry->entry_count; i++) {
        const topology_relation_entry_v1 *e = &registry->entries[i];
        size_t len = strlen(e->semantic_relation_type);
        if (len == 0) return SEMANTIC_E_INVAL;
        elpis_sha256_update(&ctx, (const uint8_t *)e->semantic_relation_type, len + 1);
        elpis_sha256_update(&ctx, (const uint8_t *)&e->numeric_relation_type, sizeof(e->numeric_relation_type));
        elpis_sha256_update(&ctx, (const uint8_t *)&e->topology_class, sizeof(e->topology_class));
        elpis_sha256_update(&ctx, (const uint8_t *)&e->traversal_cost, sizeof(e->traversal_cost));
        elpis_sha256_update(&ctx, (const uint8_t *)&e->lane, sizeof(e->lane));
        elpis_sha256_update(&ctx, (const uint8_t *)&e->polarity, sizeof(e->polarity));
        elpis_sha256_update(&ctx, (const uint8_t *)&e->classification, sizeof(e->classification));
        elpis_sha256_update(&ctx, (const uint8_t *)&e->bridge_eligible, sizeof(e->bridge_eligible));
    }

    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_registry_validate(
    const elpis_semantic_topology_relation_registry_v1 *registry) {
    if (!registry) return SEMANTIC_E_INVAL;
    if (registry->abi_version != TOPOLOGY_REGISTRY_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (registry->entry_count == 0 || registry->entry_count > TOPOLOGY_REGISTRY_MAX_ENTRIES)
        return SEMANTIC_E_INVAL;

    /* Check reserved bytes */
    for (size_t i = 0; i < sizeof(registry->reserved); i++) {
        if (registry->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    /* Validate each entry and check for duplicates */
    for (uint32_t i = 0; i < registry->entry_count; i++) {
        const topology_relation_entry_v1 *e = &registry->entries[i];
        if (strlen(e->semantic_relation_type) == 0) return SEMANTIC_E_INVAL;

        /* Check reserved */
        for (size_t j = 0; j < sizeof(e->reserved); j++) {
            if (e->reserved[j] != 0) return SEMANTIC_E_RESERVATION;
        }

        /* Validate enum ranges */
        if (e->topology_class > TOPOLOGY_CLASS_TRACE_ONLY) return SEMANTIC_E_INVAL;
        if (e->lane > TOPOLOGY_LANE_NEUTRAL) return SEMANTIC_E_INVAL;
        if (e->polarity > TOPOLOGY_POLARITY_CONTRADICTION) return SEMANTIC_E_INVAL;
        if (e->classification > TOPOLOGY_CLASSIFICATION_TRANSPORT) return SEMANTIC_E_INVAL;
        if (e->bridge_eligible > 1) return SEMANTIC_E_INVAL;

        /* Check for duplicate type names */
        for (uint32_t j = 0; j < i; j++) {
            if (strcmp(e->semantic_relation_type, registry->entries[j].semantic_relation_type) == 0)
                return SEMANTIC_E_DUPLICATE;
        }
    }
    return SEMANTIC_OK;
}

const topology_relation_entry_v1 *elpis_topology_registry_lookup(
    const elpis_semantic_topology_relation_registry_v1 *registry,
    uint32_t numeric_relation_type) {
    if (!registry) return NULL;
    for (uint32_t i = 0; i < registry->entry_count; i++) {
        if (registry->entries[i].numeric_relation_type == numeric_relation_type)
            return &registry->entries[i];
    }
    /* Also lookup by type name position */
    /* Fallback: if numeric type is in hyperedge namespace, find by offset */
    if (numeric_relation_type >= 0x20000000u) {
        uint32_t offset = numeric_relation_type - 0x20000000u - 1;
        if (offset < registry->entry_count)
            return &registry->entries[offset];
    }
    return NULL;
}

int elpis_topology_registry_is_traversable(
    const elpis_semantic_topology_relation_registry_v1 *registry,
    uint32_t numeric_relation_type) {
    const topology_relation_entry_v1 *e = elpis_topology_registry_lookup(registry, numeric_relation_type);
    if (!e) return 0; /* Unknown types fail closed */
    return (e->classification == TOPOLOGY_CLASSIFICATION_SEMANTIC) ? 1 : 0;
}

int elpis_topology_registry_get_cost(
    const elpis_semantic_topology_relation_registry_v1 *registry,
    uint32_t numeric_relation_type) {
    const topology_relation_entry_v1 *e = elpis_topology_registry_lookup(registry, numeric_relation_type);
    if (!e) return -1; /* Unknown types fail closed */
    return (int)e->traversal_cost;
}

int elpis_write_topology_registry(const char *path,
                                   const elpis_semantic_topology_relation_registry_v1 *registry) {
    if (!path || !registry) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, registry, sizeof(*registry));
    if ((size_t)w != sizeof(*registry)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}

int elpis_read_topology_registry(const char *path,
                                  elpis_semantic_topology_relation_registry_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    if ((size_t)r != sizeof(*out)) { close(fd); return SEMANTIC_E_IO; }
    close(fd);
    return elpis_topology_registry_validate(out);
}
