/* elpis_semantic/retrieval_materialization.h — Query materialization table.
 *
 * Binds P2 retrieval requirements to exact pre-existing query text and
 * embedding vector material. P3 does NOT generate text or vectors.
 *
 * Identity domain: "elpis.semantic.retrieval_materialization.v1"
 */
#ifndef ELPIS_SEMANTIC_RETRIEVAL_MATERIALIZATION_H
#define ELPIS_SEMANTIC_RETRIEVAL_MATERIALIZATION_H

#include "elpis_semantic/retrieval_requirement.h"
#include "elpis_semantic/retrieval_requirement_bundle.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MATERIALIZATION_ABI_VERSION 1u
#define MATERIALIZATION_MAX_TEXT 65536u
#define MATERIALIZATION_MAX_NAMESPACE 96u
#define MATERIALIZATION_MAX_ENTRIES 256u

/* ──────────────────────────────────────────────────────────────────── */
/* Materialization entry — binds one requirement to exact query material */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_materialization_entry_v1 {
    uint32_t                    abi_version;
    hacf_digest                 retrieval_requirement_digest;
    hacf_digest                 query_text_object_digest; /* SHA-256 of query text bytes */
    const char                 *query_text;              /* NUL-terminated, owned by table */
    uint32_t                    query_text_bytes;
    hacf_digest                 embedding_vector_digest;  /* SHA-256 of float32 vector bytes */
    hacf_digest                 embedding_profile_digest; /* SHA-256 of profile identity */
    const float                *embedding_vector;         /* float32[], owned by table */
    uint32_t                    vector_dimensions;
    const char                 *namespace_bytes;          /* NULL = no namespace filter */
    uint32_t                    namespace_bytes_len;
    hacf_digest                 namespace_digest;         /* SHA-256 of namespace bytes; zero if absent */
    uint32_t                    requested_authority_floor;/* 0..3 numeric */
    uint32_t                    requested_result_limit;   /* nonzero, bounded */
    hacf_digest                 materialization_policy_digest;
    hacf_digest                 materialization_entry_digest;
    uint8_t                     reserved[32];             /* must be zero */
} elpis_materialization_entry_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Materialization table — collection of entries, one per P2 requirement */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_materialization_table elpis_materialization_table;

/* Create an empty materialization table. Caller owns result. */
elpis_materialization_table *elpis_materialization_table_create(void);
void elpis_materialization_table_destroy(elpis_materialization_table *table);

/* Add a materialization entry. Returns SEMANTIC_OK, SEMANTIC_E_INVAL,
 * SEMANTIC_E_DUPLICATE, SEMANTIC_E_NOMEM, or SEMANTIC_E_DIGEST.
 * Validates:
 *   - requirement digest matches a requirement in the provided P2 bundle
 *   - query text bytes hash to the declared query_text_object_digest
 *   - embedding vector exists and profile matches
 *   - vector dimensions match R3 index profile (ELPIS_EMBEDDING_DIM)
 *   - vector dtype is float32
 *   - namespace bytes hash to declared namespace_digest (or zero if absent)
 *   - authority floor is 0..3
 *   - result limit is nonzero and bounded
 *   - reserved fields are zero
 * P3 does NOT: synthesize text, execute tokenizer, execute embedding model. */
int elpis_materialization_table_add(
    elpis_materialization_table *table,
    const elpis_semantic_retrieval_requirement_bundle_v1 *p2_bundle,
    const elpis_materialization_entry_v1 *entry);

/* Lookup entry by requirement digest. Returns NULL if not found. */
const elpis_materialization_entry_v1 *elpis_materialization_table_get(
    const elpis_materialization_table *table,
    const hacf_digest *requirement_digest);

/* Get entry count. */
uint32_t elpis_materialization_table_count(const elpis_materialization_table *table);

/* Get entry by index. */
const elpis_materialization_entry_v1 *elpis_materialization_table_get_at(
    const elpis_materialization_table *table, uint32_t index);

/* Compute materialization table identity digest.
 * Domain: "elpis.semantic.retrieval_materialization.v1"
 * Byte stream: domain_tag || abi_version(4 BE) || entry_count(4 BE)
 *             || for each entry: materialization_entry_digest(32) */
int elpis_materialization_table_digest(
    const elpis_materialization_table *table, hacf_digest *out);

/* Validate all entries in the table against the P2 bundle. */
int elpis_materialization_table_validate(
    const elpis_materialization_table *table,
    const elpis_semantic_retrieval_requirement_bundle_v1 *p2_bundle);

/* Compute a single entry's identity digest. */
int elpis_materialization_entry_digest(
    const elpis_materialization_entry_v1 *entry, hacf_digest *out);

/* Validate a single entry: ABI, nonzero digests where required, zero reserved,
 * valid authority floor, nonzero/bounded result limit. */
int elpis_materialization_entry_validate(
    const elpis_materialization_entry_v1 *entry);

#ifdef __cplusplus
}
#endif
#endif
