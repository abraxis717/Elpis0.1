/* elpis_semantic/retrieval_ingest.h — Evidence ingestion from RetrievalBundle.
 *
 * For each admitted RetrievalBundle item:
 *   - Verify authority meets P2 minimum floor
 *   - Create/reuse EVIDENCE_CHUNK semantic node (by chunk digest)
 *   - Create assertion with RetrievalBundle HACF package provenance
 *   - Create immutable retrieval item attachment
 *   - Create RETRIEVED_FOR transport hyperedge
 *   - Create DERIVED_FROM_RETRIEVAL_BUNDLE transport hyperedge
 *   - For context items: RETRIEVAL_CONTEXT_EXPANSION hyperedge
 *
 * P3 does NOT create: SUPPORTS, CONTRADICTS, CAUSES, REQUIRES, SAME_AS, EQUIVALENT_TO.
 * P3 does NOT infer semantic truth.
 */
#ifndef ELPIS_SEMANTIC_RETRIEVAL_INGEST_H
#define ELPIS_SEMANTIC_RETRIEVAL_INGEST_H

#include "elpis_semantic/retrieval_item_attachment.h"
#include "elpis_semantic/retrieval_requirement.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/type_registry.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RETRIEVAL_INGEST_ABI_VERSION 1u

/* Forward declarations */
struct elpis_retrieval_bundle;
struct elpis_semantic_retrieval_requirement_bundle_v1;
struct semantic_type_registry;
typedef struct elpis_retrieval_bundle elpis_retrieval_bundle;
typedef struct elpis_semantic_retrieval_requirement_bundle_v1
    elpis_semantic_retrieval_requirement_bundle_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Ingestion result for a single item */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum ingest_item_status {
    INGEST_ADMITTED             = 0,
    INGEST_AUTHORITY_REJECTED   = 1,
    INGEST_CONTEXT_PARENT_MISSING = 2,
    INGEST_INTERNAL_ERROR       = 3
} ingest_item_status;

typedef struct ingest_item_result {
    ingest_item_status status;
    uint32_t item_index;
    elpis_semantic_node_v1 evidence_node;
    elpis_semantic_assertion_v1 assertion;
    elpis_retrieval_item_attachment_v1 attachment;
    elpis_semantic_hyperedge_v1 retrieved_for_edge;
    elpis_semantic_hyperedge_v1 derived_from_bundle_edge;
} ingest_item_result;

/* ──────────────────────────────────────────────────────────────────── */
/* Ingestion batch result */
/* ──────────────────────────────────────────────────────────────────── */

#define MAX_INGEST_RESULTS 256u

typedef struct elpis_retrieval_ingest_result_v1 {
    uint32_t                    abi_version;
    uint32_t                    total_items;
    uint32_t                    admitted_count;
    uint32_t                    rejected_count;
    ingest_item_result        *items; /* array of results, allocated by caller */
    uint32_t                    items_capacity;
    hacf_digest                 requirement_digest;
    hacf_digest                 bundle_digest;
    hacf_digest                 bundle_package_digest;
    uint8_t                     reserved[32];
} elpis_retrieval_ingest_result_v1;

/* Ingest a RetrievalBundle. Caller provides results array with capacity.
 *
 * For each item:
 *  1. Verify authority >= minimum floor
 *  2. Create EVIDENCE_CHUNK node (identity = chunk_digest)
 *  3. Create assertion (provenance = bundle HACF package digest)
 *  4. Create attachment with all R3 metadata
 *  5. Create RETRIEVED_FOR hyperedge (evidence -> requirement)
 *  6. Create DERIVED_FROM_RETRIEVAL_BUNDLE hyperedge (evidence -> bundle)
 *  7. For context items: verify parent admitted, create RETRIEVAL_CONTEXT_EXPANSION
 *
 * Returns SEMANTIC_OK on success. Items array must have capacity >= bundle item count. */
int elpis_retrieval_ingest(
    elpis_retrieval_ingest_result_v1 *result,
    ingest_item_result *items_out,
    uint32_t items_capacity,
    elpis_retrieval_bundle *bundle,
    const elpis_semantic_retrieval_requirement_v1 *requirement,
    const semantic_type_registry *type_registry,
    uint32_t authority_floor);

/* Initialize ingestion result. */
void elpis_retrieval_ingest_init(elpis_retrieval_ingest_result_v1 *result);

#ifdef __cplusplus
}
#endif
#endif
