/* elpis_semantic/r3_bridge.h — R3 bridge execution for P3 retrieval bridge.
 *
 * Executes one bounded R3 hybrid retrieval per query plan and produces an
 * immutable bridge-execution receipt. Public ABI is C-compatible.
 *
 * Identity domain: "elpis.semantic.r3_bridge.v1"
 */
#ifndef ELPIS_SEMANTIC_R3_BRIDGE_H
#define ELPIS_SEMANTIC_R3_BRIDGE_H

#include "elpis_semantic/r3_query_plan.h"
#include "elpis_semantic/retrieval_materialization.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define R3_BRIDGE_ABI_VERSION 1u

/* Forward declarations from R3 public ABI */
struct elpis_corpus;
struct elpis_vector_index;
struct elpis_context_graph;
struct elpis_hybrid_retriever;
struct elpis_retrieval_bundle;
typedef struct elpis_corpus elpis_corpus;
typedef struct elpis_vector_index elpis_vector_index;
typedef struct elpis_context_graph elpis_context_graph;
typedef struct elpis_hybrid_retriever elpis_hybrid_retriever;
typedef struct elpis_retrieval_bundle elpis_retrieval_bundle;

/* ──────────────────────────────────────────────────────────────────── */
/* Bridge execution disposition */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum elpis_r3_bridge_disposition {
    R3_RETRIEVAL_COMPLETE     = 0,
    R3_RETRIEVAL_EMPTY        = 1,
    R3_EPOCH_DRIFT            = 2,
    R3_QUERY_REJECTED         = 3,
    R3_CORPUS_FAILURE         = 4,
    R3_VECTOR_FAILURE         = 5,
    R3_GRAPH_FAILURE          = 6,
    R3_INTEGRITY_FAILURE      = 7,
    R3_LIMIT_FAILURE          = 8,
    R3_INTERNAL_FAILURE       = 9
} elpis_r3_bridge_disposition;

/* ──────────────────────────────────────────────────────────────────── */
/* Bridge execution receipt */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_r3_bridge_receipt_v1 {
    uint32_t                    abi_version;
    hacf_digest                 query_plan_digest;
    hacf_digest                 r3_query_digest;
    hacf_digest                 epoch_binding_digest;
    hacf_digest                 retrieval_bundle_digest;
    hacf_digest                 retrieval_bundle_package_digest;
    uint32_t                    item_count;
    elpis_r3_bridge_disposition disposition;
    hacf_digest                 bridge_execution_digest;
    uint8_t                     reserved[32];
} elpis_r3_bridge_receipt_v1;

/* Execute one R3 retrieval for a query plan.
 * Returns SEMANTIC_OK on success (receipt filled, bundle_out owned by caller).
 * On failure, disposition is set in receipt; bundle_out is NULL.
 * Caller must call elpis_retrieval_bundle_destroy(*bundle_out) on success.
 *
 * Steps:
 *  1. Verify P2 retrieval requirement
 *  2. Verify materialization entry
 *  3. Verify epoch binding
 *  4. Construct exact elpis_hybrid_query
 *  5. Preserve exact query-text bytes
 *  6. Preserve exact float32 vector bytes
 *  7. Apply exact namespace filter
 *  8. Apply exact authority filter only if requirement carries exact constraint
 *  9. Create R3 retriever
 * 10. Execute one bounded retrieval
 * 11. Receive immutable RetrievalBundle
 * 12. Verify post-search epoch identity
 * 13. Produce immutable bridge-execution receipt */
int elpis_r3_bridge_execute(
    elpis_r3_bridge_receipt_v1 *receipt,
    elpis_retrieval_bundle **bundle_out,
    const elpis_r3_query_plan_v1 *plan,
    const elpis_materialization_entry_v1 *materialization,
    elpis_corpus *corpus,
    elpis_vector_index *index,
    const elpis_context_graph *graph);

/* Zero-initialize a receipt. Sets abi_version. */
void elpis_r3_bridge_receipt_init(elpis_r3_bridge_receipt_v1 *receipt);

/* Compute bridge execution receipt identity digest.
 * Domain: "elpis.semantic.r3_bridge.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || query_plan_digest(32)
 *             || r3_query_digest(32)
 *             || epoch_binding_digest(32)
 *             || retrieval_bundle_digest(32)
 *             || retrieval_bundle_package_digest(32)
 *             || item_count(4 BE)
 *             || disposition(4 BE). */
int elpis_r3_bridge_receipt_digest(
    const elpis_r3_bridge_receipt_v1 *receipt, hacf_digest *out);

/* Validate receipt: known ABI, zero reserved, valid disposition,
 * nonzero digests for complete disposition. */
int elpis_r3_bridge_receipt_validate(
    const elpis_r3_bridge_receipt_v1 *receipt);

/* Map R3 status code to bridge disposition. */
elpis_r3_bridge_disposition elpis_r3_bridge_disposition_from_status(int status);

#ifdef __cplusplus
}
#endif
#endif
