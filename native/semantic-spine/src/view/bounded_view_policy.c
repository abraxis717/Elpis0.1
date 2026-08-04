


/* bounded_view_policy.c — Bounded-view policy for P5. */
#include "elpis_semantic/bounded_view_policy.h"
#include "elpis_semantic/identity.h"
#include <unistd.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include "elpis/sha256.h"
#include <string.h>
#include <stdint.h>
#include <arpa/inet.h>
#include <stdio.h>

/* Simple atomic write — declared in p5_writer.c */
extern int p5_simple_write(const char *path, const uint8_t *data, size_t sz);

static void write_domain_tag(elpis_sha256_ctx *ctx, const char *domain) {
    size_t len = strlen(domain);
    uint32_t be_len = htonl((uint32_t)len);
    elpis_sha256_update(ctx, &be_len, 4);
    elpis_sha256_update(ctx, domain, len);
}

static void write_u32_be(elpis_sha256_ctx *ctx, uint32_t val) {
    uint32_t be = htonl(val);
    elpis_sha256_update(ctx, &be, 4);
}





static const char *POLICY_DOMAIN = "elpis.semantic.bounded_view_policy.v1";

void elpis_bounded_view_policy_init(
    elpis_semantic_bounded_view_policy_v1 *policy) {
    memset(policy, 0, sizeof(*policy));
    policy->abi_version = BOUNDED_VIEW_POLICY_ABI_VERSION;
}

int elpis_bounded_view_policy_default(
    elpis_semantic_bounded_view_policy_v1 *policy) {
    if (!policy) return SEMANTIC_E_INVAL;
    elpis_bounded_view_policy_init(policy);
    policy->maximum_semantic_nodes = 256;
    policy->maximum_semantic_hyperedges = 512;
    policy->maximum_incidences = 2048;
    policy->maximum_assertions = 1024;
    policy->maximum_source_spans = 256;
    policy->maximum_transport_references = 256;
    policy->maximum_embedding_references = 256;
    policy->maximum_metric_observations = 512;
    policy->maximum_graph_hops = 2;
    policy->maximum_metric_neighbors_per_seed = 8;
    policy->minimum_assertion_authority = 0;
    policy->minimum_source_authority = 0;
    memset(&policy->allowed_node_type_registry_digest, 0, HACF_DIGEST_BYTES);
    memset(&policy->allowed_hyperedge_type_registry_digest, 0, HACF_DIGEST_BYTES);
    memset(&policy->semantic_relation_allowlist_digest, 0, HACF_DIGEST_BYTES);
    memset(&policy->transport_relation_allowlist_digest, 0, HACF_DIGEST_BYTES);
    memset(&policy->metric_profile_allowlist_digest, 0, HACF_DIGEST_BYTES);
    policy->mandatory_seed_policy = CLOSURE_FAIL_CLOSED;
    policy->conflict_closure_policy = CLOSURE_FAIL_CLOSED;
    policy->provenance_closure_policy = CLOSURE_FAIL_CLOSED;
    policy->scope_closure_policy = CLOSURE_FAIL_CLOSED;
    policy->qualifier_closure_policy = CLOSURE_FAIL_CLOSED;
    policy->transport_inclusion_policy = OVERFLOW_OMIT_OPTIONAL;
    policy->metric_supplement_policy = OVERFLOW_OMIT_OPTIONAL;
    policy->overflow_behavior = OVERFLOW_FAIL_CLOSED;
    policy->omission_receipt_policy = CLOSURE_FAIL_CLOSED;
    policy->policy_flags = BOUNDED_VIEW_FLAG_NONE;
    elpis_bounded_view_policy_identity(policy, &policy->policy_identity);
    return SEMANTIC_OK;
}

int elpis_bounded_view_policy_identity(
    const elpis_semantic_bounded_view_policy_v1 *policy, hacf_digest *out) {
    if (!policy || !out || policy->abi_version != BOUNDED_VIEW_POLICY_ABI_VERSION)
        return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, POLICY_DOMAIN);
    uint32_t ver = policy->abi_version;
    write_u32_be(&ctx, ver);
    write_u32_be(&ctx, policy->maximum_semantic_nodes);
    write_u32_be(&ctx, policy->maximum_semantic_hyperedges);
    write_u32_be(&ctx, policy->maximum_incidences);
    write_u32_be(&ctx, policy->maximum_assertions);
    write_u32_be(&ctx, policy->maximum_source_spans);
    write_u32_be(&ctx, policy->maximum_transport_references);
    write_u32_be(&ctx, policy->maximum_embedding_references);
    write_u32_be(&ctx, policy->maximum_metric_observations);
    write_u32_be(&ctx, policy->maximum_graph_hops);
    write_u32_be(&ctx, policy->maximum_metric_neighbors_per_seed);
    write_u32_be(&ctx, policy->minimum_assertion_authority);
    write_u32_be(&ctx, policy->minimum_source_authority);
    elpis_sha256_update(&ctx, policy->allowed_node_type_registry_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->allowed_hyperedge_type_registry_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->semantic_relation_allowlist_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->transport_relation_allowlist_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, policy->metric_profile_allowlist_digest.bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, policy->mandatory_seed_policy);
    write_u32_be(&ctx, policy->conflict_closure_policy);
    write_u32_be(&ctx, policy->provenance_closure_policy);
    write_u32_be(&ctx, policy->scope_closure_policy);
    write_u32_be(&ctx, policy->qualifier_closure_policy);
    write_u32_be(&ctx, policy->transport_inclusion_policy);
    write_u32_be(&ctx, policy->metric_supplement_policy);
    write_u32_be(&ctx, policy->overflow_behavior);
    write_u32_be(&ctx, policy->omission_receipt_policy);
    write_u32_be(&ctx, policy->policy_flags);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_bounded_view_policy_validate(
    const elpis_semantic_bounded_view_policy_v1 *policy) {
    if (!policy) return SEMANTIC_E_INVAL;
    if (policy->abi_version != BOUNDED_VIEW_POLICY_ABI_VERSION) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(policy->reserved); i++) {
        if (policy->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    if (policy->maximum_graph_hops == 0) return SEMANTIC_E_INVAL;
    if (policy->maximum_metric_neighbors_per_seed == 0) return SEMANTIC_E_INVAL;
    if (policy->maximum_semantic_nodes == 0) return SEMANTIC_E_INVAL;
    if ((policy->policy_flags & ~BOUNDED_VIEW_FLAG_MASK) != 0) return SEMANTIC_E_INVAL;
    if (policy->mandatory_seed_policy > 1) return SEMANTIC_E_INVAL;
    if (policy->conflict_closure_policy > 1) return SEMANTIC_E_INVAL;
    if (policy->provenance_closure_policy > 1) return SEMANTIC_E_INVAL;
    if (policy->scope_closure_policy > 1) return SEMANTIC_E_INVAL;
    if (policy->qualifier_closure_policy > 1) return SEMANTIC_E_INVAL;
    if (policy->transport_inclusion_policy > 1) return SEMANTIC_E_INVAL;
    if (policy->metric_supplement_policy > 1) return SEMANTIC_E_INVAL;
    if (policy->overflow_behavior > 1) return SEMANTIC_E_INVAL;
    if (policy->omission_receipt_policy > 1) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_write_bounded_view_policy(const char *path,
    const elpis_semantic_bounded_view_policy_v1 *policy) {
    if (!path || !policy) return SEMANTIC_E_INVAL;
    return (int)p5_simple_write(path, (const uint8_t *)policy, sizeof(*policy));
}

int elpis_read_bounded_view_policy(const char *path,
    elpis_semantic_bounded_view_policy_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;
    fseek(f, 0, SEEK_END); long sz = ftell(f);
    if (sz != (long)sizeof(*out)) { fclose(f); return SEMANTIC_E_IO; }
    fseek(f, 0, SEEK_SET); size_t rd = fread(out, 1, sizeof(*out), f);
    fclose(f); if (rd != sizeof(*out)) return SEMANTIC_E_IO;
    int rc = elpis_bounded_view_policy_validate(out);
    if (rc != SEMANTIC_OK) return rc;
    hacf_digest computed; elpis_bounded_view_policy_identity(out, &computed);
    if (memcmp(&computed, &out->policy_identity, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_E_DIGEST;
    return SEMANTIC_OK;
}
