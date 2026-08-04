/* retrieval_materialization.c — Query materialization table implementation.
 *
 * Binds P2 retrieval requirements to exact pre-existing query text and
 * embedding vector material. P3 does NOT generate text or vectors.
 */
#include "elpis_semantic/retrieval_materialization.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>

struct elpis_materialization_table {
    uint32_t                    count;
    uint32_t                    capacity;
    elpis_materialization_entry_v1 *entries;
};

static uint8_t be32_buf(uint32_t v) {
    uint8_t b[4];
    uint32_t be = htonl(v);
    memcpy(b, &be, 4);
    return b[0]; /* just to suppress unused warning */
}

static void write_be32(elpis_sha256_ctx *h, uint32_t v) {
    uint32_t be = htonl(v);
    elpis_sha256_update(h, &be, 4);
}

int elpis_materialization_entry_validate(
    const elpis_materialization_entry_v1 *entry)
{
    if (!entry) return SEMANTIC_E_INVAL;
    if (entry->abi_version != MATERIALIZATION_ABI_VERSION) return SEMANTIC_E_INVAL;

    /* Reserved must be zero */
    if (memcmp(entry->reserved, "\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0\0", 32) != 0)
        return SEMANTIC_E_INVAL;

    /* Query text must be present and nonzero length */
    if (!entry->query_text || entry->query_text_bytes == 0)
        return SEMANTIC_E_INVAL;

    /* Embedding vector must be present */
    if (!entry->embedding_vector)
        return SEMANTIC_E_INVAL;

    /* Authority floor 0..3 */
    if (entry->requested_authority_floor > 3)
        return SEMANTIC_E_INVAL;

    /* Result limit nonzero */
    if (entry->requested_result_limit == 0)
        return SEMANTIC_E_INVAL;

    /* Result limit bounded */
    if (entry->requested_result_limit > 256)
        return SEMANTIC_E_INVAL;

    /* Query text digest must be nonzero */
    {
        uint8_t zero[32];
        memset(zero, 0, 32);
        if (memcmp(entry->query_text_object_digest.bytes, zero, 32) == 0)
            return SEMANTIC_E_INVAL;
    }

    /* Embedding vector digest must be nonzero */
    {
        uint8_t zero[32];
        memset(zero, 0, 32);
        if (memcmp(entry->embedding_vector_digest.bytes, zero, 32) == 0)
            return SEMANTIC_E_INVAL;
    }

    return SEMANTIC_OK;
}

int elpis_materialization_entry_digest(
    const elpis_materialization_entry_v1 *entry, hacf_digest *out)
{
    if (!entry || !out) return SEMANTIC_E_INVAL;

    static const char domain[] = "elpis.semantic.retrieval_materialization.v1";
    size_t domain_len = strlen(domain);
    uint32_t be_len = htonl((uint32_t)domain_len);

    elpis_sha256_ctx h;
    elpis_sha256_init(&h);

    /* Domain tag */
    elpis_sha256_update(&h, &be_len, 4);
    elpis_sha256_update(&h, domain, domain_len);

    /* abi_version BE32 */
    write_be32(&h, entry->abi_version);

    /* retrieval_requirement_digest (32 bytes) */
    elpis_sha256_update(&h, entry->retrieval_requirement_digest.bytes, 32);

    /* query_text_object_digest (32 bytes) */
    elpis_sha256_update(&h, entry->query_text_object_digest.bytes, 32);

    /* query_text_bytes BE32 */
    write_be32(&h, entry->query_text_bytes);

    /* query text bytes */
    if (entry->query_text && entry->query_text_bytes > 0)
        elpis_sha256_update(&h, entry->query_text, entry->query_text_bytes);

    /* embedding_vector_digest (32 bytes) */
    elpis_sha256_update(&h, entry->embedding_vector_digest.bytes, 32);

    /* embedding_profile_digest (32 bytes) */
    elpis_sha256_update(&h, entry->embedding_profile_digest.bytes, 32);

    /* vector_dimensions BE32 */
    write_be32(&h, entry->vector_dimensions);

    /* vector bytes */
    if (entry->embedding_vector && entry->vector_dimensions > 0) {
        size_t vec_bytes = (size_t)entry->vector_dimensions * sizeof(float);
        elpis_sha256_update(&h, entry->embedding_vector, vec_bytes);
    }

    /* namespace: length BE32 + bytes (or zero length) */
    write_be32(&h, entry->namespace_bytes_len);
    if (entry->namespace_bytes && entry->namespace_bytes_len > 0)
        elpis_sha256_update(&h, entry->namespace_bytes, entry->namespace_bytes_len);

    /* namespace_digest (32 bytes) */
    elpis_sha256_update(&h, entry->namespace_digest.bytes, 32);

    /* requested_authority_floor BE32 */
    write_be32(&h, entry->requested_authority_floor);

    /* requested_result_limit BE32 */
    write_be32(&h, entry->requested_result_limit);

    /* materialization_policy_digest (32 bytes) */
    elpis_sha256_update(&h, entry->materialization_policy_digest.bytes, 32);

    uint8_t d[32];
    elpis_sha256_final(&h, d);
    memcpy(out->bytes, d, 32);
    return SEMANTIC_OK;
}

elpis_materialization_table *elpis_materialization_table_create(void) {
    elpis_materialization_table *table = calloc(1, sizeof(*table));
    if (!table) return NULL;
    table->capacity = 8;
    table->entries = calloc(table->capacity, sizeof(elpis_materialization_entry_v1));
    if (!table->entries) {
        free(table);
        return NULL;
    }
    return table;
}

void elpis_materialization_table_destroy(elpis_materialization_table *table) {
    if (!table) return;
    free(table->entries);
    free(table);
}

static int digest_is_zero(const hacf_digest *d) {
    uint8_t zero[32];
    memset(zero, 0, 32);
    return memcmp(d->bytes, zero, 32) == 0;
}

int elpis_materialization_table_add(
    elpis_materialization_table *table,
    const elpis_semantic_retrieval_requirement_bundle_v1 *p2_bundle,
    const elpis_materialization_entry_v1 *entry)
{
    if (!table || !entry || !p2_bundle) return SEMANTIC_E_INVAL;

    /* Validate entry basics */
    if (elpis_materialization_entry_validate(entry) != SEMANTIC_OK)
        return SEMANTIC_E_INVAL;

    /* Check requirement exists in P2 bundle */
    {
        int found = 0;
        for (uint32_t i = 0; i < p2_bundle->retrieval_count; i++) {
            if (hacf_digest_cmp(&entry->retrieval_requirement_digest,
                               &p2_bundle->retrieval_requirement_digests[i]) == 0) {
                found = 1;
                break;
            }
        }
        if (!found) return SEMANTIC_E_NOTFOUND;
    }

    /* Check no duplicate requirement digest in table */
    for (uint32_t i = 0; i < table->count; i++) {
        if (hacf_digest_cmp(&entry->retrieval_requirement_digest,
                           &table->entries[i].retrieval_requirement_digest) == 0) {
            return SEMANTIC_E_DUPLICATE;
        }
    }

    /* Verify query text bytes hash to declared digest */
    {
        uint8_t computed[32];
        elpis_sha256(entry->query_text, entry->query_text_bytes, computed);
        if (memcmp(computed, entry->query_text_object_digest.bytes, 32) != 0)
            return SEMANTIC_E_DIGEST;
    }

    /* Verify namespace digest if namespace present */
    if (entry->namespace_bytes && entry->namespace_bytes_len > 0) {
        uint8_t ns_hash[32];
        elpis_sha256(entry->namespace_bytes, entry->namespace_bytes_len, ns_hash);
        if (memcmp(ns_hash, entry->namespace_digest.bytes, 32) != 0)
            return SEMANTIC_E_DIGEST;
    } else if (!digest_is_zero(&entry->namespace_digest)) {
        /* No namespace but digest is nonzero — mismatch */
        return SEMANTIC_E_DIGEST;
    }

    /* Grow table if needed */
    if (table->count >= table->capacity) {
        uint32_t new_cap = table->capacity * 2;
        if (new_cap > MATERIALIZATION_MAX_ENTRIES) new_cap = MATERIALIZATION_MAX_ENTRIES;
        if (table->count >= MATERIALIZATION_MAX_ENTRIES)
            return SEMANTIC_E_INVAL;
        void *new_entries = realloc(table->entries,
            new_cap * sizeof(elpis_materialization_entry_v1));
        if (!new_entries) return SEMANTIC_E_NOMEM;
        table->entries = (elpis_materialization_entry_v1 *)new_entries;
        table->capacity = new_cap;
    }

    /* Copy entry */
    memcpy(&table->entries[table->count], entry, sizeof(elpis_materialization_entry_v1));

    /* Compute entry digest */
    if (elpis_materialization_entry_digest(&table->entries[table->count],
        &table->entries[table->count].materialization_entry_digest) != SEMANTIC_OK)
        return SEMANTIC_E_DIGEST;

    table->count++;
    return SEMANTIC_OK;
}

const elpis_materialization_entry_v1 *elpis_materialization_table_get(
    const elpis_materialization_table *table,
    const hacf_digest *requirement_digest)
{
    if (!table || !requirement_digest) return NULL;
    for (uint32_t i = 0; i < table->count; i++) {
        if (hacf_digest_cmp(&table->entries[i].retrieval_requirement_digest,
                           requirement_digest) == 0) {
            return &table->entries[i];
        }
    }
    return NULL;
}

uint32_t elpis_materialization_table_count(const elpis_materialization_table *table) {
    return table ? table->count : 0;
}

const elpis_materialization_entry_v1 *elpis_materialization_table_get_at(
    const elpis_materialization_table *table, uint32_t index)
{
    if (!table || index >= table->count) return NULL;
    return &table->entries[index];
}

int elpis_materialization_table_digest(
    const elpis_materialization_table *table, hacf_digest *out)
{
    if (!table || !out) return SEMANTIC_E_INVAL;

    static const char domain[] = "elpis.semantic.retrieval_materialization.v1";
    size_t domain_len = strlen(domain);
    uint32_t be_len = htonl((uint32_t)domain_len);

    elpis_sha256_ctx h;
    elpis_sha256_init(&h);

    elpis_sha256_update(&h, &be_len, 4);
    elpis_sha256_update(&h, domain, domain_len);

    uint32_t be = htonl(MATERIALIZATION_ABI_VERSION);
    elpis_sha256_update(&h, &be, 4);

    be = htonl(table->count);
    elpis_sha256_update(&h, &be, 4);

    for (uint32_t i = 0; i < table->count; i++) {
        elpis_sha256_update(&h, table->entries[i].materialization_entry_digest.bytes, 32);
    }

    uint8_t d[32];
    elpis_sha256_final(&h, d);
    memcpy(out->bytes, d, 32);
    return SEMANTIC_OK;
}

int elpis_materialization_table_validate(
    const elpis_materialization_table *table,
    const elpis_semantic_retrieval_requirement_bundle_v1 *p2_bundle)
{
    if (!table || !p2_bundle) return SEMANTIC_E_INVAL;

    for (uint32_t i = 0; i < table->count; i++) {
        if (elpis_materialization_entry_validate(&table->entries[i]) != SEMANTIC_OK)
            return SEMANTIC_E_INVAL;

        /* Verify requirement exists in bundle */
        int found = 0;
        for (uint32_t j = 0; j < p2_bundle->retrieval_count; j++) {
            if (hacf_digest_cmp(&table->entries[i].retrieval_requirement_digest,
                               &p2_bundle->retrieval_requirement_digests[j]) == 0) {
                found = 1;
                break;
            }
        }
        if (!found) return SEMANTIC_E_NOTFOUND;
    }

    return SEMANTIC_OK;
}
