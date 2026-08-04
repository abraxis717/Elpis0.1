


/* downstream_handoff.c — Downstream handoff ABI for P5. */
#include "elpis_semantic/downstream_handoff.h"
#include "elpis_semantic/identity.h"
#include <unistd.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include "elpis_semantic/bounded_semantic_view.h"
#include "elpis_semantic/context_reevaluation.h"
#include "elpis_semantic/context_deficit_report.h"
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





static const char *HANDOFF_DOMAIN = "elpis.semantic.downstream_handoff.v1";

void elpis_downstream_handoff_init(
    elpis_semantic_downstream_handoff_v1 *handoff) {
    memset(handoff, 0, sizeof(*handoff));
    handoff->abi_version = DOWNSTREAM_HANDOFF_ABI_VERSION;
}

int elpis_downstream_handoff_construct(
    const elpis_semantic_bounded_semantic_view_v1 *bounded_view,
    const elpis_semantic_context_reevaluation_v1  *reevaluation,
    const elpis_semantic_context_requirement_set_v1 *rebound_set,
    const elpis_semantic_context_deficit_report_v1 *P2_report,
    elpis_semantic_downstream_handoff_v1          *handoff)
{
    if (!bounded_view || !reevaluation || !rebound_set || !P2_report || !handoff)
        return SEMANTIC_E_INVAL;

    /* Verify bounded view is valid */
    int rc = elpis_bounded_semantic_view_validate(bounded_view);
    if (rc != SEMANTIC_OK) return rc;

    elpis_downstream_handoff_init(handoff);
    handoff->handoff_kind = HANDOFF_KIND_SEMANTIC_TOPOLOGY_COMPILER_INPUT;

    /* Bind root query overlay */
    memcpy(&handoff->root_query_overlay_digest,
           &bounded_view->root_query_overlay_digest, HACF_DIGEST_BYTES);

    /* Bind bounded semantic view digest */
    memcpy(&handoff->bounded_semantic_view_digest,
           &bounded_view->bounded_view_digest, HACF_DIGEST_BYTES);

    /* Bind all four plane digests */
    memcpy(&handoff->semantic_plane_digest,
           &bounded_view->semantic_plane_digest, HACF_DIGEST_BYTES);
    memcpy(&handoff->provenance_plane_digest,
           &bounded_view->provenance_plane_digest, HACF_DIGEST_BYTES);
    memcpy(&handoff->metric_plane_digest,
           &bounded_view->metric_plane_digest, HACF_DIGEST_BYTES);
    memcpy(&handoff->control_plane_digest,
           &bounded_view->control_plane_digest, HACF_DIGEST_BYTES);

    /* Bind requirement set */
    memcpy(&handoff->requirement_set_digest,
           &rebound_set->requirement_set_identity, HACF_DIGEST_BYTES);

    /* Bind context report */
    memcpy(&handoff->context_report_digest,
           &P2_report->report_identity, HACF_DIGEST_BYTES);

    /* Bind bounded view policy */
    memcpy(&handoff->bounded_view_policy_digest,
           &bounded_view->bounded_view_policy_digest, HACF_DIGEST_BYTES);

    /* Registry digests — zero for now (external) */
    memset(&handoff->type_registry_chain_digest, 0, HACF_DIGEST_BYTES);
    memset(&handoff->authority_registry_digest, 0, HACF_DIGEST_BYTES);

    /* Payload dependency manifest digest */
    memset(&handoff->payload_dependency_manifest_digest, 0, HACF_DIGEST_BYTES);

    /* Feature schema digest */
    memset(&handoff->feature_schema_digest, 0, HACF_DIGEST_BYTES);

    /* Handoff policy digest */
    memset(&handoff->handoff_policy_digest, 0, HACF_DIGEST_BYTES);

    /* HACF package digest */
    memcpy(&handoff->HACF_package_digest,
           &bounded_view->HACF_package_digest, HACF_DIGEST_BYTES);

    /* Compute handoff identity */
    elpis_downstream_handoff_identity(handoff, &handoff->handoff_digest);

    return SEMANTIC_OK;
}

int elpis_downstream_handoff_identity(
    const elpis_semantic_downstream_handoff_v1 *handoff, hacf_digest *out) {
    if (!handoff || !out ||
        handoff->abi_version != DOWNSTREAM_HANDOFF_ABI_VERSION)
        return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, HANDOFF_DOMAIN);
    uint32_t ver = handoff->abi_version;
    write_u32_be(&ctx, ver);
    write_u32_be(&ctx, handoff->handoff_kind);
    elpis_sha256_update(&ctx, handoff->root_query_overlay_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->bounded_semantic_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->semantic_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->provenance_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->metric_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->control_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->type_registry_chain_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->authority_registry_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->requirement_set_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->context_report_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->bounded_view_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->payload_dependency_manifest_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->feature_schema_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->handoff_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_downstream_handoff_validate(
    const elpis_semantic_downstream_handoff_v1 *handoff) {
    if (!handoff) return SEMANTIC_E_INVAL;
    if (handoff->abi_version != DOWNSTREAM_HANDOFF_ABI_VERSION)
        return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(handoff->reserved); i++) {
        if (handoff->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }
    /* Valid handoff kind */
    if (handoff->handoff_kind > 0) return SEMANTIC_E_INVAL;

    /* Non-zero required digests */
    for (int i = 0; i < HACF_DIGEST_BYTES; i++) {
        if (handoff->bounded_semantic_view_digest.bytes[i] != 0) break;
        if (i == HACF_DIGEST_BYTES - 1) return SEMANTIC_E_INVAL;
    }
    for (int i = 0; i < HACF_DIGEST_BYTES; i++) {
        if (handoff->semantic_plane_digest.bytes[i] != 0) break;
        if (i == HACF_DIGEST_BYTES - 1) return SEMANTIC_E_INVAL;
    }

    /* No Grid81 coupling: verify no Grid81-related fields (they don't exist) */
    /* This is a structural guarantee by the ABI — no Grid81 fields present */

    return SEMANTIC_OK;
}

int elpis_handoff_payload_manifest_identity(
    const handoff_payload_dependency_manifest_v1 *manifest, hacf_digest *out) {
    if (!manifest || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, "elpis.semantic.handoff_payload_manifest.v1");
    write_u32_be(&ctx, manifest->abi_version);
    write_u32_be(&ctx, manifest->semantic_payload_count);
    for (uint32_t i = 0; i < manifest->semantic_payload_count; i++)
        elpis_sha256_update(&ctx, manifest->semantic_payload_digests[i].bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, manifest->claim_payload_count);
    for (uint32_t i = 0; i < manifest->claim_payload_count; i++)
        elpis_sha256_update(&ctx, manifest->claim_payload_digests[i].bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, manifest->source_document_count);
    for (uint32_t i = 0; i < manifest->source_document_count; i++)
        elpis_sha256_update(&ctx, manifest->source_document_digests[i].bytes, HACF_DIGEST_BYTES);
    write_u32_be(&ctx, manifest->embedding_vector_count);
    for (uint32_t i = 0; i < manifest->embedding_vector_count; i++)
        elpis_sha256_update(&ctx, manifest->embedding_vector_digests[i].bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, manifest->type_registry_manifest_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, manifest->authority_registry_manifest_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_write_downstream_handoff(const char *path,
    const elpis_semantic_downstream_handoff_v1 *handoff) {
    if (!path || !handoff) return SEMANTIC_E_INVAL;
    return (int)p5_simple_write(path, (const uint8_t *)handoff, sizeof(*handoff));
}

int elpis_read_downstream_handoff(const char *path,
    elpis_semantic_downstream_handoff_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;
    fseek(f, 0, SEEK_END); long sz = ftell(f);
    if (sz != (long)sizeof(*out)) { fclose(f); return SEMANTIC_E_IO; }
    fseek(f, 0, SEEK_SET); size_t rd = fread(out, 1, sizeof(*out), f);
    fclose(f); if (rd != sizeof(*out)) return SEMANTIC_E_IO;
    int rc = elpis_downstream_handoff_validate(out);
    if (rc != SEMANTIC_OK) return rc;
    hacf_digest computed;
    elpis_downstream_handoff_identity(out, &computed);
    if (memcmp(&computed, &out->handoff_digest, HACF_DIGEST_BYTES) != 0)
        return SEMANTIC_E_DIGEST;
    return SEMANTIC_OK;
}
