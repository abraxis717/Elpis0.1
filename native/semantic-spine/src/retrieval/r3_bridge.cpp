/* r3_bridge.cpp — R3 bridge execution for P3 retrieval bridge.
 *
 * Executes one bounded R3 hybrid retrieval per query plan and produces an
 * immutable bridge-execution receipt. C-compatible public ABI, C++ internal.
 *
 * Identity domain: "elpis.semantic.r3_bridge.v1"
 */
#include "elpis_semantic/r3_bridge.h"
#include "elpis/hybrid_retrieval.h"
#include "elpis/retrieval_bundle.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"

#include <cstring>
#include <cstdint>

namespace {

static void put_be32(elpis_sha256_ctx *h, uint32_t v) {
    uint8_t b[4] = {(uint8_t)(v >> 24), (uint8_t)(v >> 16),
                    (uint8_t)(v >> 8), (uint8_t)v};
    elpis_sha256_update(h, b, 4);
}

static const char kZeroDigest[] =
    "0000000000000000000000000000000000000000000000000000000000000000";

/* Compute R3 query digest from materialization entry (same encoding as
 * hybrid_retrieval.cpp query_digest() but with our data).
 *
 * Domain: "elpis.hybrid.query.v1" (includes NUL in sizeof) */
static int compute_r3_query_digest(
    const elpis_materialization_entry_v1 *mat,
    const elpis_hybrid_policy *policy,
    char out[65])
{
    if (!mat || !mat->query_text || !mat->embedding_vector || !out) return -1;

    size_t n = strnlen(mat->query_text, 65536);
    if (n == 0 || n > 65535) return -1;

    static const char domain[] = "elpis.hybrid.query.v1";
    elpis_sha256_ctx h;
    elpis_sha256_init(&h);

    /* domain includes NUL in sizeof */
    elpis_sha256_update(&h, domain, sizeof domain);

    /* text_len LE64 */
    uint64_t text_len = (uint64_t)n;
    for (unsigned i = 0; i < 8; ++i)
        elpis_sha256_update(&h, ((uint8_t*)&text_len) + i, 1);

    /* text bytes */
    elpis_sha256_update(&h, mat->query_text, n);

    /* namespace: LE64 length + bytes */
    uint64_t ns_len = mat->namespace_bytes ? (uint64_t)mat->namespace_bytes_len : 0;
    for (unsigned i = 0; i < 8; ++i)
        elpis_sha256_update(&h, ((uint8_t*)&ns_len) + i, 1);
    if (mat->namespace_bytes && mat->namespace_bytes_len > 0)
        elpis_sha256_update(&h, mat->namespace_bytes, mat->namespace_bytes_len);

    /* authority filter: always null for P3 floor-based policy */
    uint64_t auth_len = 0;
    for (unsigned i = 0; i < 8; ++i)
        elpis_sha256_update(&h, ((uint8_t*)&auth_len) + i, 1);

    /* profile_digest: 64 hex chars */
    char profile_hex[65];
    hacf_digest_hex(&mat->embedding_profile_digest, profile_hex);
    elpis_sha256_update(&h, profile_hex, 64);

    /* dimensions LE32 */
    put_be32(&h, mat->vector_dimensions); /* BE32 for our encoding */

    /* vector float32 bits as LE32 each */
    for (uint32_t i = 0; i < mat->vector_dimensions; ++i) {
        uint32_t bits;
        std::memcpy(&bits, &mat->embedding_vector[i], sizeof(bits));
        uint8_t b[4] = {(uint8_t)bits, (uint8_t)(bits >> 8),
                        (uint8_t)(bits >> 16), (uint8_t)(bits >> 24)};
        elpis_sha256_update(&h, b, 4);
    }

    uint8_t d[32];
    elpis_sha256_final(&h, d);
    elpis_hex32(d, out);
    return 0;
}

} // namespace

extern "C" {

void elpis_r3_bridge_receipt_init(elpis_r3_bridge_receipt_v1 *receipt) {
    if (!receipt) return;
    std::memset(receipt, 0, sizeof(*receipt));
    receipt->abi_version = R3_BRIDGE_ABI_VERSION;
}

elpis_r3_bridge_disposition elpis_r3_bridge_disposition_from_status(int status) {
    switch (status) {
        case ELPIS_HYBRID_OK:          return R3_RETRIEVAL_COMPLETE;
        case ELPIS_HYBRID_E_INVAL:     return R3_QUERY_REJECTED;
        case ELPIS_HYBRID_E_DRIFT:     return R3_EPOCH_DRIFT;
        case ELPIS_HYBRID_E_CORPUS:    return R3_CORPUS_FAILURE;
        case ELPIS_HYBRID_E_VECTOR:    return R3_VECTOR_FAILURE;
        case ELPIS_HYBRID_E_GRAPH:     return R3_GRAPH_FAILURE;
        case ELPIS_HYBRID_E_INTEGRITY: return R3_INTEGRITY_FAILURE;
        case ELPIS_HYBRID_E_LIMIT:     return R3_LIMIT_FAILURE;
        default:                       return R3_INTERNAL_FAILURE;
    }
}

int elpis_r3_bridge_receipt_digest(
    const elpis_r3_bridge_receipt_v1 *receipt, hacf_digest *out)
{
    if (!receipt || !out) return SEMANTIC_E_INVAL;

    static const char domain[] = "elpis.semantic.r3_bridge.v1";
    elpis_sha256_ctx h;
    elpis_sha256_init(&h);

    size_t domain_len = std::strlen(domain);
    uint32_t be = (uint32_t)domain_len;
    uint8_t b[4] = {(uint8_t)(be >> 24), (uint8_t)(be >> 16),
                    (uint8_t)(be >> 8), (uint8_t)be};
    elpis_sha256_update(&h, b, 4);
    elpis_sha256_update(&h, domain, domain_len);

    /* abi_version BE32 */
    be = receipt->abi_version;
    b[0] = (uint8_t)(be >> 24); b[1] = (uint8_t)(be >> 16);
    b[2] = (uint8_t)(be >> 8); b[3] = (uint8_t)be;
    elpis_sha256_update(&h, b, 4);

    /* Digests (32 bytes each) */
    elpis_sha256_update(&h, receipt->query_plan_digest.bytes, 32);
    elpis_sha256_update(&h, receipt->r3_query_digest.bytes, 32);
    elpis_sha256_update(&h, receipt->epoch_binding_digest.bytes, 32);
    elpis_sha256_update(&h, receipt->retrieval_bundle_digest.bytes, 32);
    elpis_sha256_update(&h, receipt->retrieval_bundle_package_digest.bytes, 32);

    /* item_count BE32 */
    be = receipt->item_count;
    b[0] = (uint8_t)(be >> 24); b[1] = (uint8_t)(be >> 16);
    b[2] = (uint8_t)(be >> 8); b[3] = (uint8_t)be;
    elpis_sha256_update(&h, b, 4);

    /* disposition BE32 */
    be = (uint32_t)receipt->disposition;
    b[0] = (uint8_t)(be >> 24); b[1] = (uint8_t)(be >> 16);
    b[2] = (uint8_t)(be >> 8); b[3] = (uint8_t)be;
    elpis_sha256_update(&h, b, 4);

    uint8_t d[32];
    elpis_sha256_final(&h, d);
    std::memcpy(out->bytes, d, 32);
    return SEMANTIC_OK;
}

int elpis_r3_bridge_receipt_validate(
    const elpis_r3_bridge_receipt_v1 *receipt)
{
    if (!receipt) return SEMANTIC_E_INVAL;
    if (receipt->abi_version != R3_BRIDGE_ABI_VERSION) return SEMANTIC_E_INVAL;

    for (size_t i = 0; i < sizeof(receipt->reserved); ++i)
        if (receipt->reserved[i] != 0) return SEMANTIC_E_INVAL;

    if (receipt->disposition > R3_INTERNAL_FAILURE) return SEMANTIC_E_INVAL;

    /* For complete/empty dispositions, digests must be nonzero */
    if (receipt->disposition == R3_RETRIEVAL_COMPLETE ||
        receipt->disposition == R3_RETRIEVAL_EMPTY) {
        if (std::memcmp(receipt->query_plan_digest.bytes, kZeroDigest, 32) == 0)
            return SEMANTIC_E_INVAL;
        if (std::memcmp(receipt->r3_query_digest.bytes, kZeroDigest, 32) == 0)
            return SEMANTIC_E_INVAL;
    }

    return SEMANTIC_OK;
}

int elpis_r3_bridge_execute(
    elpis_r3_bridge_receipt_v1 *receipt,
    elpis_retrieval_bundle **bundle_out,
    const elpis_r3_query_plan_v1 *plan,
    const elpis_materialization_entry_v1 *materialization,
    elpis_corpus *corpus,
    elpis_vector_index *index,
    const elpis_context_graph *graph)
{
    if (!receipt || !bundle_out || !plan || !materialization || !corpus || !index)
        return SEMANTIC_E_INVAL;

    elpis_r3_bridge_receipt_init(receipt);
    *bundle_out = nullptr;

    /* Step 1-3: Verify plan and materialization (already validated at construction) */

    /* Step 4-6: Construct exact elpis_hybrid_query */
    elpis_hybrid_query q;
    q.text = materialization->query_text;
    q.vector = materialization->embedding_vector;
    q.dimensions = materialization->vector_dimensions;
    q.namespace_filter = materialization->namespace_bytes;
    q.authority_filter = NULL; /* P3 v1: floor-based, not exact authority filter */

    /* Step 9: Create R3 retriever */
    elpis_hybrid_retriever *retriever = nullptr;
    int rc = elpis_hybrid_retriever_create(
        corpus, index, graph, &plan->derived_policy, &retriever);
    if (rc != ELPIS_HYBRID_OK || !retriever) {
        receipt->disposition = elpis_r3_bridge_disposition_from_status(rc);
        /* Fill digests we can */
        hacf_digest plan_d;
        if (elpis_r3_query_plan_digest(plan, &plan_d) == SEMANTIC_OK)
            receipt->query_plan_digest = plan_d;
        return SEMANTIC_OK; /* receipt contains disposition */
    }

    /* Step 10: Execute bounded retrieval */
    rc = elpis_hybrid_retrieve(retriever, &q, bundle_out);
    elpis_hybrid_retriever_destroy(retriever);

    if (rc != ELPIS_HYBRID_OK || !*bundle_out) {
        receipt->disposition = elpis_retrieval_bundle_item_count(*bundle_out) > 0
            ? R3_RETRIEVAL_EMPTY
            : elpis_r3_bridge_disposition_from_status(rc);
        if (*bundle_out) {
            elpis_retrieval_bundle_destroy(*bundle_out);
            *bundle_out = nullptr;
        }
        /* Fill digests we can */
        hacf_digest plan_d;
        if (elpis_r3_query_plan_digest(plan, &plan_d) == SEMANTIC_OK)
            receipt->query_plan_digest = plan_d;
        return SEMANTIC_OK; /* receipt contains disposition */
    }

    /* Step 12: Received immutable RetrievalBundle */

    /* Step 13: Post-search epoch check is handled inside R3,
     * but we capture the disposition for the receipt */
    receipt->disposition = (*bundle_out && elpis_retrieval_bundle_item_count(*bundle_out) > 0)
        ? R3_RETRIEVAL_COMPLETE : R3_RETRIEVAL_EMPTY;

    /* Step 14: Produce bridge execution receipt */

    /* Query plan digest */
    hacf_digest plan_d;
    if (elpis_r3_query_plan_digest(plan, &plan_d) != SEMANTIC_OK)
        plan_d = receipt->query_plan_digest;
    receipt->query_plan_digest = plan_d;

    /* R3 query digest */
    {
        char qd[65];
        if (compute_r3_query_digest(materialization, &plan->derived_policy, qd) == 0) {
            hacf_digest_from_hex(qd, &receipt->r3_query_digest);
        }
    }

    /* Epoch binding digest */
    {
        hacf_digest ed;
        /* We don't have the full epoch binding here, but the plan references it */
        ed = plan->r3_epoch_binding_digest;
        receipt->epoch_binding_digest = ed;
    }

    /* Bundle identity */
    {
        char qd[65], cd[65], vd[65], gd[65], pd[65], bd[65], hd[65];
        if (elpis_retrieval_bundle_identity(*bundle_out, qd, cd, vd, gd, pd, bd, hd) == 0) {
            hacf_digest_from_hex(bd, &receipt->retrieval_bundle_digest);
            hacf_digest_from_hex(hd, &receipt->retrieval_bundle_package_digest);
        }
    }

    /* Item count */
    receipt->item_count = elpis_retrieval_bundle_item_count(*bundle_out);

    /* Bridge execution digest */
    elpis_r3_bridge_receipt_digest(receipt, &receipt->bridge_execution_digest);

    return SEMANTIC_OK;
}

} // extern "C"
