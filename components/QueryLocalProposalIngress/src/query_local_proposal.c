#include "query_local_proposal.h"
#include "elpis/sha256.h"
#include <arpa/inet.h>
#include <stddef.h>
#include <string.h>

static int digest_zero(const hacf_digest *d) {
    static const uint8_t z[HACF_DIGEST_BYTES] = {0};
    return memcmp(d->bytes, z, HACF_DIGEST_BYTES) == 0;
}
static int digest_eq(const hacf_digest *a, const hacf_digest *b) {
    return memcmp(a->bytes, b->bytes, HACF_DIGEST_BYTES) == 0;
}
static int zero_bytes(const uint8_t *p, size_t n) {
    for (size_t i = 0; i < n; ++i) if (p[i] != 0) return 0;
    return 1;
}
static void put_u32(elpis_sha256_ctx *ctx, uint32_t v) {
    uint32_t be = htonl(v);
    elpis_sha256_update(ctx, &be, 4);
}
static void put_domain(elpis_sha256_ctx *ctx, const char *domain) {
    put_u32(ctx, (uint32_t)strlen(domain));
    elpis_sha256_update(ctx, domain, strlen(domain));
}

int elpis_query_local_proposal_identity(
    const elpis_query_local_proposal_v1 *p,
    hacf_digest *out)
{
    if (!p || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    put_domain(&ctx, "elpis.semantic.query_local_proposal.v1");
    put_u32(&ctx, p->abi_version);
    elpis_sha256_update(&ctx, p->query_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, p->proposal_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, p->candidate_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, p->hacf_corpus_manifest_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, p->hacf_context_graph_manifest_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, p->registry_contract_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, p->native_registry_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, p->representation_policy_digest.bytes, HACF_DIGEST_BYTES);
    put_u32(&ctx, p->candidate_status);
    put_u32(&ctx, p->semantic_authority);
    put_u32(&ctx, p->admission_authority);
    put_u32(&ctx, p->execution_authority);
    put_u32(&ctx, p->runtime_admission);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_query_local_proposal_validate(
    const elpis_query_local_proposal_v1 *p,
    const elpis_query_local_context_v1 *e)
{
    if (!p || !e) return SEMANTIC_E_INVAL;
    if (p->abi_version != ELPIS_QUERY_LOCAL_PROPOSAL_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (p->candidate_status != ELPIS_QUERY_LOCAL_PROPOSAL_STATUS_PROPOSED_UNADMITTED) return SEMANTIC_E_INVAL;
    if (p->semantic_authority || p->admission_authority ||
        p->execution_authority || p->runtime_admission) return SEMANTIC_E_AUTHORITY;
    if (!zero_bytes(p->reserved, sizeof p->reserved)) return SEMANTIC_E_INVAL;

    if (digest_zero(&p->query_digest) ||
        digest_zero(&p->proposal_digest) ||
        digest_zero(&p->candidate_digest) ||
        digest_zero(&p->hacf_corpus_manifest_digest) ||
        digest_zero(&p->hacf_context_graph_manifest_digest) ||
        digest_zero(&p->registry_contract_digest) ||
        digest_zero(&p->native_registry_digest) ||
        digest_zero(&p->representation_policy_digest))
        return SEMANTIC_E_DIGEST;

    if (!digest_eq(&p->query_digest, &e->query_digest) ||
        !digest_eq(&p->proposal_digest, &e->proposal_digest) ||
        !digest_eq(&p->hacf_corpus_manifest_digest, &e->hacf_corpus_manifest_digest) ||
        !digest_eq(&p->hacf_context_graph_manifest_digest, &e->hacf_context_graph_manifest_digest) ||
        !digest_eq(&p->registry_contract_digest, &e->registry_contract_digest) ||
        !digest_eq(&p->native_registry_digest, &e->native_registry_digest) ||
        !digest_eq(&p->representation_policy_digest, &e->representation_policy_digest))
        return SEMANTIC_E_DIGEST;

    hacf_digest expected;
    if (elpis_query_local_proposal_identity(p, &expected) != SEMANTIC_OK)
        return SEMANTIC_E_DIGEST;
    return digest_eq(&expected, &p->envelope_identity) ? SEMANTIC_OK : SEMANTIC_E_DIGEST;
}

static int receipt_identity(
    const elpis_query_local_representation_receipt_v1 *r,
    hacf_digest *out)
{
    if (!r || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    put_domain(&ctx, "elpis.semantic.query_local_representation_receipt.v1");
    put_u32(&ctx, r->abi_version);
    elpis_sha256_update(&ctx, r->envelope_identity.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, r->node_identity.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, r->assertion_identity.bytes, HACF_DIGEST_BYTES);
    put_u32(&ctx, r->disposition);
    put_u32(&ctx, r->semantic_authority);
    put_u32(&ctx, r->admission_authority);
    put_u32(&ctx, r->execution_authority);
    put_u32(&ctx, r->runtime_admission);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_query_local_representation_receipt_validate(
    const elpis_query_local_representation_receipt_v1 *r)
{
    if (!r) return SEMANTIC_E_INVAL;
    if (r->abi_version != ELPIS_QUERY_LOCAL_REPRESENTATION_RECEIPT_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (r->disposition != ELPIS_QUERY_LOCAL_REPRESENTATION_RECEIPT_REPRESENTABLE) return SEMANTIC_E_INVAL;
    if (r->semantic_authority || r->admission_authority ||
        r->execution_authority || r->runtime_admission) return SEMANTIC_E_AUTHORITY;
    if (!zero_bytes(r->reserved, sizeof r->reserved)) return SEMANTIC_E_INVAL;
    hacf_digest expected;
    if (receipt_identity(r, &expected) != SEMANTIC_OK) return SEMANTIC_E_DIGEST;
    return digest_eq(&expected, &r->receipt_identity) ? SEMANTIC_OK : SEMANTIC_E_DIGEST;
}

int elpis_query_local_proposal_materialize(
    const elpis_query_local_proposal_v1 *p,
    const elpis_query_local_context_v1 *expected,
    elpis_semantic_node_v1 *node,
    elpis_semantic_assertion_v1 *a,
    elpis_query_local_representation_receipt_v1 *r)
{
    if (!node || !a || !r) return SEMANTIC_E_INVAL;
    int rc = elpis_query_local_proposal_validate(p, expected);
    if (rc != SEMANTIC_OK) return rc;

    memset(node, 0, sizeof *node);
    node->abi_version = SEMANTIC_ABI_VERSION;
    node->node_type = ELPIS_QUERY_LOCAL_PROPOSAL_NODE_TYPE;
    node->semantic_flags = SEMANTIC_NODE_FLAG_EXTERNAL;
    node->payload_digest = p->envelope_identity;
    if (elpis_semantic_node_identity(node, &node->node_identity) != SEMANTIC_OK)
        return SEMANTIC_E_DIGEST;

    memset(a, 0, sizeof *a);
    a->abi_version = SEMANTIC_ABI_VERSION;
    a->asserted_object_kind = SEMANTIC_OBJECT_KIND_NODE;
    a->asserted_object_digest = node->node_identity;
    a->provenance_digest = p->proposal_digest;
    a->authority = 0;
    a->assertion_flags = SEMANTIC_ASSERTION_FLAG_NONE;
    if (elpis_semantic_assertion_identity(a, &a->assertion_identity) != SEMANTIC_OK)
        return SEMANTIC_E_DIGEST;

    memset(r, 0, sizeof *r);
    r->abi_version = ELPIS_QUERY_LOCAL_REPRESENTATION_RECEIPT_ABI_VERSION;
    r->envelope_identity = p->envelope_identity;
    r->node_identity = node->node_identity;
    r->assertion_identity = a->assertion_identity;
    r->disposition = ELPIS_QUERY_LOCAL_REPRESENTATION_RECEIPT_REPRESENTABLE;
    if (receipt_identity(r, &r->receipt_identity) != SEMANTIC_OK) return SEMANTIC_E_DIGEST;
    return elpis_query_local_representation_receipt_validate(r);
}

int elpis_query_local_overlay_bind_context(
    semantic_query_overlay *overlay,
    const semantic_type_registry *registry,
    const elpis_query_local_context_v1 *c)
{
    if (!overlay || !registry || !c) return SEMANTIC_E_INVAL;
    if (!digest_eq(&overlay->query_digest, &c->query_digest)) return SEMANTIC_E_DIGEST;

    hacf_digest native_registry;
    if (semantic_type_registry_digest(registry, &native_registry) != SEMANTIC_OK)
        return SEMANTIC_E_DIGEST;
    if (!digest_eq(&native_registry, &c->native_registry_digest))
        return SEMANTIC_E_DIGEST;

    if (!digest_zero(&overlay->overlay_policy_digest) &&
        !digest_eq(&overlay->overlay_policy_digest, &c->representation_policy_digest))
        return SEMANTIC_E_DIGEST;

    overlay->overlay_policy_digest = c->representation_policy_digest;

    if (semantic_overlay_add_external_dependency(overlay, &c->registry_contract_digest) != SEMANTIC_OK) return SEMANTIC_E_NOMEM;
    if (semantic_overlay_add_external_dependency(overlay, &c->native_registry_digest) != SEMANTIC_OK) return SEMANTIC_E_NOMEM;
    if (semantic_overlay_add_external_dependency(overlay, &c->proposal_digest) != SEMANTIC_OK) return SEMANTIC_E_NOMEM;
    if (semantic_overlay_add_external_dependency(overlay, &c->hacf_corpus_manifest_digest) != SEMANTIC_OK) return SEMANTIC_E_NOMEM;
    if (semantic_overlay_add_external_dependency(overlay, &c->hacf_context_graph_manifest_digest) != SEMANTIC_OK) return SEMANTIC_E_NOMEM;
    return SEMANTIC_OK;
}
