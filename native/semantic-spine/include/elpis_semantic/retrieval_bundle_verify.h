/* elpis_semantic/retrieval_bundle_verify.h — Independent RetrievalBundle verification.
 *
 * Verifies every returned bundle independently of the mere R3 success status.
 * Recomputes expected R3 query digest and verifies all item fields.
 */
#ifndef ELPIS_SEMANTIC_RETRIEVAL_BUNDLE_VERIFY_H
#define ELPIS_SEMANTIC_RETRIEVAL_BUNDLE_VERIFY_H

#include "elpis_semantic/r3_epoch.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BUNDLE_VERIFY_ABI_VERSION 1u

/* Forward declaration from R3 public ABI */
struct elpis_retrieval_bundle;
typedef struct elpis_retrieval_bundle elpis_retrieval_bundle;

/* ──────────────────────────────────────────────────────────────────── */
/* Verification result codes */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum bundle_verify_status {
    BUNDLE_VERIFY_OK              = 0,
    BUNDLE_VERIFY_QUERY_MISMATCH  = 1,
    BUNDLE_VERIFY_CORPUS_MISMATCH = 2,
    BUNDLE_VERIFY_INDEX_MISMATCH  = 3,
    BUNDLE_VERIFY_GRAPH_MISMATCH  = 4,
    BUNDLE_VERIFY_POLICY_MISMATCH = 5,
    BUNDLE_VERIFY_ITEM_TEXT_MISMATCH = 6,
    BUNDLE_VERIFY_METADATA_CONFLICT = 7,
    BUNDLE_VERIFY_INVALID_KIND    = 8,
    BUNDLE_VERIFY_INVALID_SOURCE_MASK = 9,
    BUNDLE_VERIFY_INVALID_GRAPH_PARENT = 10,
    BUNDLE_VERIFY_IMPOSSIBLE_HOP  = 11,
    BUNDLE_VERIFY_DUPLICATE_RANK  = 12,
    BUNDLE_VERIFY_NONCANONICAL_ORDER = 13,
    BUNDLE_VERIFY_PACKAGE_MISMATCH = 14
} bundle_verify_status;

/* ──────────────────────────────────────────────────────────────────── */
/* Verification result record */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct bundle_verify_result {
    bundle_verify_status status;
    uint32_t item_index;  /* failing item index, or 0xFFFFFFFF */
    char detail[128];
} bundle_verify_result;

/* Verify a RetrievalBundle against the expected epoch binding and query plan.
 * Returns SEMANTIC_OK with result->status == BUNDLE_VERIFY_OK on success.
 *
 * Verifies:
 *   - Query digest matches expected
 *   - Corpus manifest digest matches
 *   - Vector index manifest digest matches
 *   - Graph snapshot digest matches (or all-zero when no graph)
 *   - Fusion policy digest matches
 *   - Every item: text digest, chunk digest, doc digest, namespace, authority
 *   - Every item: valid source mask (subset of LEXICAL|DENSE|GRAPH)
 *   - Every item: valid item kind (PRIMARY or CONTEXT)
 *   - Every item: graph_hop is 0 or 1
 *   - Every item: graph_parent_digest all-zero for primary items
 *   - No duplicate final ranks
 *   - Canonical ordering: higher fusion_score_key first, then lower chunk_digest
 *   - Package identity matches recompute */
int elpis_bundle_verify(
    bundle_verify_result *result,
    elpis_retrieval_bundle *bundle,
    const elpis_r3_epoch_binding_v1 *epoch_binding,
    const char *expected_query_digest);

#ifdef __cplusplus
}
#endif
#endif
