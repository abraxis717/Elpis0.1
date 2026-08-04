/* r3_epoch.cpp — R3 epoch binding implementation for P3 retrieval bridge.
 *
 * Binds exact R3 retrieval epoch: corpus, vector index, optional context
 * graph, hybrid policy. Provides drift detection — no automatic retry.
 *
 * Identity domain: "elpis.semantic.r3_epoch.v1"
 */
#include "elpis_semantic/r3_epoch.h"
#include "elpis_semantic/identity.h"
#include "elpis/corpus.h"
#include "elpis/vector_index.h"
#include "elpis/context_graph.h"
#include "elpis/hybrid_retrieval.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include "elpis/vector_result.h"

#include <cstring>
#include <cstdint>

namespace {

static const char kZeroDigest[] =
    "0000000000000000000000000000000000000000000000000000000000000000";

static void put_be32(elpis_sha256_ctx *h, uint32_t v) {
    uint8_t b[4] = {(uint8_t)(v >> 24), (uint8_t)(v >> 16),
                    (uint8_t)(v >> 8), (uint8_t)v};
    elpis_sha256_update(h, b, sizeof b);
}

} // namespace

extern "C" {

void elpis_r3_epoch_binding_init(elpis_r3_epoch_binding_v1 *binding) {
    if (!binding) return;
    std::memset(binding, 0, sizeof(*binding));
    binding->abi_version = R3_EPOCH_ABI_VERSION;
    binding->r3_abi_version = ELPIS_HYBRID_ABI_VERSION;
    std::memcpy(binding->context_graph_digest, kZeroDigest, 65);
}

int elpis_r3_epoch_binding_create(
    elpis_r3_epoch_binding_v1 *binding,
    elpis_corpus *corpus,
    elpis_vector_index *index,
    const elpis_context_graph *graph,
    const elpis_hybrid_policy *policy,
    const hacf_digest *bridge_policy)
{
    if (!binding || !corpus || !index || !policy)
        return SEMANTIC_E_INVAL;

    elpis_r3_epoch_binding_init(binding);

    /* Capture corpus manifest digest */
    if (elpis_corpus_manifest_json(corpus, nullptr, binding->corpus_manifest_digest) != 0)
        return SEMANTIC_E_INVAL;

    /* Capture vector index manifest digest */
    if (elpis_vector_index_manifest_json(index, nullptr, binding->vector_index_manifest_digest) != 0)
        return SEMANTIC_E_INVAL;

    /* Capture profile digest and verify index is bound to this corpus */
    char index_corpus[65];
    if (elpis_vector_index_profile_digest(index, binding->vector_index_profile_digest,
                                          index_corpus) != ELPIS_VEC_OK)
        return SEMANTIC_E_INVAL;
    std::memcpy(binding->index_corpus_binding, index_corpus, 65);

    /* Verify index is bound to the same corpus */
    if (std::strcmp(binding->index_corpus_binding, binding->corpus_manifest_digest) != 0)
        return SEMANTIC_E_DIGEST; /* corpus mismatch */

    /* Nonzero check */
    if (std::strcmp(binding->corpus_manifest_digest, kZeroDigest) == 0 ||
        std::strcmp(binding->vector_index_manifest_digest, kZeroDigest) == 0)
        return SEMANTIC_E_INVAL;

    /* Context graph digest */
    if (graph) {
        if (elpis_context_graph_digest(graph, binding->context_graph_digest) != 0)
            return SEMANTIC_E_INVAL;
    } else {
        std::memcpy(binding->context_graph_digest, kZeroDigest, 65);
    }

    /* Hybrid policy digest */
    if (elpis_hybrid_policy_digest(policy, binding->hybrid_policy_digest) != 0)
        return SEMANTIC_E_INVAL;

    /* R3 ABI version */
    binding->r3_abi_version = ELPIS_HYBRID_ABI_VERSION;

    /* Bridge policy digest */
    if (bridge_policy) {
        binding->bridge_policy_digest = *bridge_policy;
    }

    /* Compute epoch binding digest */
    return elpis_r3_epoch_binding_digest(binding, &binding->epoch_binding_digest);
}

int elpis_r3_epoch_binding_digest(
    const elpis_r3_epoch_binding_v1 *binding, hacf_digest *out)
{
    if (!binding || !out) return SEMANTIC_E_INVAL;

    static const char domain[] = "elpis.semantic.r3_epoch.v1";
    elpis_sha256_ctx h;
    elpis_sha256_init(&h);

    /* Domain tag with BE length */
    size_t domain_len = std::strlen(domain);
    uint32_t be_len = (uint32_t)domain_len;
    uint8_t b[4] = {(uint8_t)(be_len >> 24), (uint8_t)(be_len >> 16),
                    (uint8_t)(be_len >> 8), (uint8_t)be_len};
    elpis_sha256_update(&h, b, 4);
    elpis_sha256_update(&h, domain, domain_len);

    /* abi_version BE32 */
    be_len = binding->abi_version;
    b[0] = (uint8_t)(be_len >> 24); b[1] = (uint8_t)(be_len >> 16);
    b[2] = (uint8_t)(be_len >> 8); b[3] = (uint8_t)be_len;
    elpis_sha256_update(&h, b, 4);

    /* Digests as hex bytes (64 chars each, no NUL) */
    elpis_sha256_update(&h, binding->corpus_manifest_digest, 64);
    elpis_sha256_update(&h, binding->vector_index_manifest_digest, 64);
    elpis_sha256_update(&h, binding->vector_index_profile_digest, 64);
    elpis_sha256_update(&h, binding->index_corpus_binding, 64);
    elpis_sha256_update(&h, binding->context_graph_digest, 64);
    elpis_sha256_update(&h, binding->hybrid_policy_digest, 64);

    /* r3_abi_version BE32 */
    be_len = binding->r3_abi_version;
    b[0] = (uint8_t)(be_len >> 24); b[1] = (uint8_t)(be_len >> 16);
    b[2] = (uint8_t)(be_len >> 8); b[3] = (uint8_t)be_len;
    elpis_sha256_update(&h, b, 4);

    /* bridge_policy_digest (32 bytes binary) */
    elpis_sha256_update(&h, binding->bridge_policy_digest.bytes, 32);

    uint8_t d[32];
    elpis_sha256_final(&h, d);
    std::memcpy(out->bytes, d, 32);
    return SEMANTIC_OK;
}

int elpis_r3_epoch_binding_validate(
    const elpis_r3_epoch_binding_v1 *binding)
{
    if (!binding) return SEMANTIC_E_INVAL;
    if (binding->abi_version != R3_EPOCH_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (binding->r3_abi_version != ELPIS_HYBRID_ABI_VERSION) return SEMANTIC_E_INVAL;

    /* Check reserved is zero */
    for (size_t i = 0; i < sizeof(binding->reserved); ++i)
        if (binding->reserved[i] != 0) return SEMANTIC_E_INVAL;

    /* Nonzero required digests */
    if (std::strcmp(binding->corpus_manifest_digest, kZeroDigest) == 0)
        return SEMANTIC_E_INVAL;
    if (std::strcmp(binding->vector_index_manifest_digest, kZeroDigest) == 0)
        return SEMANTIC_E_INVAL;
    if (std::strcmp(binding->vector_index_profile_digest, kZeroDigest) == 0)
        return SEMANTIC_E_INVAL;
    if (std::strcmp(binding->hybrid_policy_digest, kZeroDigest) == 0)
        return SEMANTIC_E_INVAL;

    /* Index must be bound to same corpus */
    if (std::strcmp(binding->index_corpus_binding, binding->corpus_manifest_digest) != 0)
        return SEMANTIC_E_DIGEST;

    return SEMANTIC_OK;
}

int elpis_r3_epoch_check_drift(
    const elpis_r3_epoch_binding_v1 *binding,
    elpis_corpus *corpus,
    elpis_vector_index *index)
{
    if (!binding || !corpus || !index) return SEMANTIC_E_INVAL;

    char current_corpus[65], current_index[65];
    if (elpis_corpus_manifest_json(corpus, nullptr, current_corpus) != 0)
        return SEMANTIC_E_INVAL;
    if (elpis_vector_index_manifest_json(index, nullptr, current_index) != 0)
        return SEMANTIC_E_INVAL;

    if (std::strcmp(current_corpus, binding->corpus_manifest_digest) != 0 ||
        std::strcmp(current_index, binding->vector_index_manifest_digest) != 0)
        return SEMANTIC_E_DIGEST; /* drift detected */

    return SEMANTIC_OK;
}

int elpis_r3_epoch_check_drift_post(
    const elpis_r3_epoch_binding_v1 *binding,
    elpis_corpus *corpus,
    elpis_vector_index *index)
{
    /* Post-search drift check is identical to pre-check */
    return elpis_r3_epoch_check_drift(binding, corpus, index);
}

} // extern "C"
