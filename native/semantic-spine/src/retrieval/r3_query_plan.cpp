/* r3_query_plan.cpp — R3 query plan derivation for P3 retrieval bridge.
 *
 * One logical R3 query plan per P2 retrieval requirement. Derives an R3
 * hybrid policy from a sealed template + requirement constraints.
 *
 * Identity domain: "elpis.semantic.r3_query_plan.v1"
 */
#include "elpis_semantic/r3_query_plan.h"
#include "elpis_semantic/identity.h"
#include "elpis/hybrid_retrieval.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"

#include <cstring>
#include <cstdint>
#include <algorithm>

namespace {

static void put_be32(elpis_sha256_ctx *h, uint32_t v) {
    uint8_t b[4] = {(uint8_t)(v >> 24), (uint8_t)(v >> 16),
                    (uint8_t)(v >> 8), (uint8_t)v};
    elpis_sha256_update(h, b, 4);
}

static void put_le32(elpis_sha256_ctx *h, uint32_t v) {
    uint8_t b[4] = {(uint8_t)v, (uint8_t)(v >> 8),
                    (uint8_t)(v >> 16), (uint8_t)(v >> 24)};
    elpis_sha256_update(h, b, 4);
}

} // namespace

extern "C" {

void elpis_r3_query_plan_init(elpis_r3_query_plan_v1 *plan) {
    if (!plan) return;
    std::memset(plan, 0, sizeof(*plan));
    plan->abi_version = R3_QUERY_PLAN_ABI_VERSION;
}

int elpis_r3_query_plan_derive(
    elpis_r3_query_plan_v1 *plan,
    const elpis_semantic_retrieval_requirement_v1 *requirement,
    const elpis_materialization_entry_v1 *materialization,
    const elpis_r3_epoch_binding_v1 *epoch_binding,
    const elpis_hybrid_policy *template_policy)
{
    if (!plan || !requirement || !materialization || !epoch_binding || !template_policy)
        return SEMANTIC_E_INVAL;

    elpis_r3_query_plan_init(plan);

    /* Bind retrieval requirement digest */
    hacf_digest req_digest;
    if (elpis_retrieval_requirement_identity(requirement, &req_digest) != SEMANTIC_OK)
        return SEMANTIC_E_INVAL;
    plan->retrieval_requirement_digest = req_digest;

    /* Bind materialization entry digest */
    hacf_digest mat_digest;
    if (elpis_materialization_entry_digest(materialization, &mat_digest) != SEMANTIC_OK)
        return SEMANTIC_E_INVAL;
    plan->materialization_entry_digest = mat_digest;

    /* Bind epoch binding digest */
    hacf_digest epoch_digest;
    if (elpis_r3_epoch_binding_digest(epoch_binding, &epoch_digest) != SEMANTIC_OK)
        return SEMANTIC_E_INVAL;
    plan->r3_epoch_binding_digest = epoch_digest;

    /* Derive policy from template */
    plan->derived_policy = *template_policy;

    uint32_t total_limit = materialization->requested_result_limit;
    if (total_limit == 0 || total_limit > ELPIS_HYBRID_MAX_BUNDLE_ITEMS)
        return SEMANTIC_E_INVAL;

    plan->derived_policy.total_limit = total_limit;
    plan->derived_policy.primary_limit =
        std::min(template_policy->primary_limit, total_limit);
    plan->derived_policy.graph_seed_limit =
        std::min(template_policy->graph_seed_limit, plan->derived_policy.primary_limit);

    /* min_graph_authority = max(template, requirement floor) */
    uint32_t floor = requirement->requested_min_authority;
    if (floor > 3) floor = 0; /* clamp invalid values */
    plan->derived_policy.min_graph_authority =
        std::max(template_policy->min_graph_authority, floor);

    /* Validate derived policy */
    if (elpis_hybrid_policy_validate(&plan->derived_policy) != 0)
        return SEMANTIC_E_INVAL;

    /* Namespace */
    if (materialization->namespace_bytes && materialization->namespace_bytes_len > 0) {
        plan->namespace_digest = materialization->namespace_digest;
    } else {
        std::memset(&plan->namespace_digest, 0, sizeof(plan->namespace_digest));
    }

    /* Authority floor */
    plan->authority_floor = requirement->requested_min_authority;
    if (plan->authority_floor > 3)
        return SEMANTIC_E_INVAL;

    /* Exact authority: not set in P3 v1 (floor-based policy) */
    plan->has_exact_authority = 0;
    plan->exact_authority = NULL;

    /* Result limit */
    plan->requested_result_limit = materialization->requested_result_limit;

    /* Compute query plan digest */
    return elpis_r3_query_plan_digest(plan, &plan->query_plan_digest);
}

int elpis_r3_query_plan_digest(
    const elpis_r3_query_plan_v1 *plan, hacf_digest *out)
{
    if (!plan || !out) return SEMANTIC_E_INVAL;

    static const char domain[] = "elpis.semantic.r3_query_plan.v1";
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
    be_len = plan->abi_version;
    b[0] = (uint8_t)(be_len >> 24); b[1] = (uint8_t)(be_len >> 16);
    b[2] = (uint8_t)(be_len >> 8); b[3] = (uint8_t)be_len;
    elpis_sha256_update(&h, b, 4);

    /* Digests (32 bytes each) */
    elpis_sha256_update(&h, plan->retrieval_requirement_digest.bytes, 32);
    elpis_sha256_update(&h, plan->materialization_entry_digest.bytes, 32);
    elpis_sha256_update(&h, plan->r3_epoch_binding_digest.bytes, 32);

    /* Derived policy fields as LE32 (same encoding as R3 policy digest) */
    const elpis_hybrid_policy *p = &plan->derived_policy;
    const uint32_t vals[] = {
        p->abi_version, p->lexical_limit, p->dense_limit,
        p->primary_limit, p->graph_seed_limit, p->graph_neighbors_per_seed,
        p->total_limit, p->rrf_k, p->lexical_weight, p->dense_weight,
        p->min_graph_authority
    };
    for (size_t i = 0; i < sizeof(vals) / sizeof(vals[0]); ++i)
        put_le32(&h, vals[i]);

    /* namespace_digest (32 bytes) */
    elpis_sha256_update(&h, plan->namespace_digest.bytes, 32);

    /* authority_floor BE32 */
    be_len = plan->authority_floor;
    b[0] = (uint8_t)(be_len >> 24); b[1] = (uint8_t)(be_len >> 16);
    b[2] = (uint8_t)(be_len >> 8); b[3] = (uint8_t)be_len;
    elpis_sha256_update(&h, b, 4);

    /* has_exact_authority BE32 */
    be_len = plan->has_exact_authority;
    b[0] = (uint8_t)(be_len >> 24); b[1] = (uint8_t)(be_len >> 16);
    b[2] = (uint8_t)(be_len >> 8); b[3] = (uint8_t)be_len;
    elpis_sha256_update(&h, b, 4);

    /* requested_result_limit BE32 */
    be_len = plan->requested_result_limit;
    b[0] = (uint8_t)(be_len >> 24); b[1] = (uint8_t)(be_len >> 16);
    b[2] = (uint8_t)(be_len >> 8); b[3] = (uint8_t)be_len;
    elpis_sha256_update(&h, b, 4);

    uint8_t d[32];
    elpis_sha256_final(&h, d);
    std::memcpy(out->bytes, d, 32);
    return SEMANTIC_OK;
}

int elpis_r3_query_plan_validate(
    const elpis_r3_query_plan_v1 *plan)
{
    if (!plan) return SEMANTIC_E_INVAL;
    if (plan->abi_version != R3_QUERY_PLAN_ABI_VERSION) return SEMANTIC_E_INVAL;

    /* Check reserved is zero */
    for (size_t i = 0; i < sizeof(plan->reserved); ++i)
        if (plan->reserved[i] != 0) return SEMANTIC_E_INVAL;

    /* Validate derived policy via R3 */
    if (elpis_hybrid_policy_validate(&plan->derived_policy) != 0)
        return SEMANTIC_E_INVAL;

    /* Authority floor 0..3 */
    if (plan->authority_floor > 3) return SEMANTIC_E_INVAL;

    /* Result limit nonzero */
    if (plan->requested_result_limit == 0) return SEMANTIC_E_INVAL;

    return SEMANTIC_OK;
}

} // extern "C"
