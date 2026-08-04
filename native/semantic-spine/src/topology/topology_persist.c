/* topology_persist.c — IR, receipt, handoff persistence. */
#include "elpis_semantic/semantic_topology_ir.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis_semantic/topology_handoff.h"
#include "elpis/cascade.h"
#include <string.h>

int elpis_write_topology_IR(const char *path,
    const elpis_semantic_topology_IR_v1 *ir) {
    if (!path || !ir) return SEMANTIC_E_INVAL;
    if (ir->abi_version != TOPOLOGY_IR_ABI_VERSION) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, ir, sizeof(*ir));
    if ((size_t)w != sizeof(*ir)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}

int elpis_read_topology_IR(const char *path,
    elpis_semantic_topology_IR_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    if ((size_t)r != sizeof(*out)) { close(fd); return SEMANTIC_E_IO; }
    close(fd);
    if (out->abi_version != TOPOLOGY_IR_ABI_VERSION) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

int elpis_write_compile_receipt(const char *path,
    const elpis_topology_compile_receipt_v1 *receipt) {
    if (!path || !receipt) return SEMANTIC_E_INVAL;
    if (receipt->abi_version != TOPOLOGY_IR_ABI_VERSION) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, receipt, sizeof(*receipt));
    if ((size_t)w != sizeof(*receipt)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}

int elpis_read_compile_receipt(const char *path,
    elpis_topology_compile_receipt_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    if ((size_t)r != sizeof(*out)) { close(fd); return SEMANTIC_E_IO; }
    close(fd);
    if (out->abi_version != TOPOLOGY_IR_ABI_VERSION) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}

/* ─── Handoff ─── */

void elpis_topology_handoff_init(elpis_semantic_topology_handoff_v1 *handoff) {
    if (!handoff) return;
    memset(handoff, 0, sizeof(*handoff));
    handoff->abi_version = TOPOLOGY_HANDOFF_ABI_VERSION;
    handoff->handoff_kind = TOPOLOGY_HANDOFF_SEMANTIC_TO_GRID81_COMPILER_INPUT;
    /* Set all P7 boundary flags */
    handoff->P7_may_assign_discrete_placement = 1;
    handoff->P7_may_not_alter_relation_types = 1;
    handoff->P7_may_not_alter_authority = 1;
    handoff->P7_may_not_remove_conflict_polarity = 1;
    handoff->P7_may_not_treat_metric_as_semantic = 1;
    handoff->local_ordinal_is_not_grid81_cell = 1;
    handoff->one_vertex_not_one_cell = 1;
}

int elpis_topology_handoff_construct(
    elpis_semantic_topology_handoff_v1 *handoff,
    const elpis_topology_compile_context *ctx,
    const elpis_semantic_downstream_handoff_v1 *P5_handoff) {
    if (!handoff || !ctx || !P5_handoff) return SEMANTIC_E_INVAL;
    elpis_topology_handoff_init(handoff);

    memcpy(&handoff->root_query_overlay_digest, &P5_handoff->root_query_overlay_digest, HACF_DIGEST_BYTES);
    memcpy(&handoff->P5_bounded_view_digest, &P5_handoff->bounded_semantic_view_digest, HACF_DIGEST_BYTES);
    memcpy(&handoff->topology_IR_digest, &ctx->IR.IR_digest, HACF_DIGEST_BYTES);
    memcpy(&handoff->topology_policy_digest, &ctx->policy.policy_identity, HACF_DIGEST_BYTES);
    memcpy(&handoff->relation_registry_digest, &ctx->registry.registry_identity, HACF_DIGEST_BYTES);
    memcpy(&handoff->type_registry_chain_digest, &P5_handoff->type_registry_chain_digest, HACF_DIGEST_BYTES);
    memcpy(&handoff->authority_registry_digest, &P5_handoff->authority_registry_digest, HACF_DIGEST_BYTES);
    memcpy(&handoff->ordered_addresses_digest, &ctx->addresses.address_plane_digest, HACF_DIGEST_BYTES);
    memcpy(&handoff->ordered_constraints_digest, &ctx->constraints.constraint_plane_digest, HACF_DIGEST_BYTES);
    memcpy(&handoff->feature_schema_digest, &P5_handoff->feature_schema_digest, HACF_DIGEST_BYTES);
    memcpy(&handoff->dependency_manifest_digest, &P5_handoff->payload_dependency_manifest_digest, HACF_DIGEST_BYTES);

    /* Compute handoff identity */
    hacf_digest id;
    elpis_topology_handoff_identity(handoff, &id);
    memcpy(handoff->handoff_digest.bytes, id.bytes, HACF_DIGEST_BYTES);

    return SEMANTIC_OK;
}

int elpis_topology_handoff_identity(
    const elpis_semantic_topology_handoff_v1 *handoff, hacf_digest *out) {
    if (!handoff || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology_handoff.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&handoff->abi_version, sizeof(handoff->abi_version));
    elpis_sha256_update(&ctx, (const uint8_t *)&handoff->handoff_kind, sizeof(handoff->handoff_kind));
    elpis_sha256_update(&ctx, handoff->root_query_overlay_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->P5_bounded_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->topology_IR_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->topology_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->relation_registry_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->type_registry_chain_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->authority_registry_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->ordered_addresses_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->ordered_constraints_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->feature_schema_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, handoff->dependency_manifest_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_handoff_validate(
    const elpis_semantic_topology_handoff_v1 *handoff) {
    if (!handoff) return SEMANTIC_E_INVAL;
    if (handoff->abi_version != TOPOLOGY_HANDOFF_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (handoff->handoff_kind != TOPOLOGY_HANDOFF_SEMANTIC_TO_GRID81_COMPILER_INPUT)
        return SEMANTIC_E_INVAL;

    /* P7 boundary flags must be set */
    if (!handoff->P7_may_assign_discrete_placement) return SEMANTIC_E_INVAL;
    if (!handoff->P7_may_not_alter_relation_types) return SEMANTIC_E_INVAL;
    if (!handoff->P7_may_not_alter_authority) return SEMANTIC_E_INVAL;
    if (!handoff->P7_may_not_remove_conflict_polarity) return SEMANTIC_E_INVAL;
    if (!handoff->P7_may_not_treat_metric_as_semantic) return SEMANTIC_E_INVAL;
    if (!handoff->local_ordinal_is_not_grid81_cell) return SEMANTIC_E_INVAL;
    if (!handoff->one_vertex_not_one_cell) return SEMANTIC_E_INVAL;

    /* Check reserved */
    for (size_t i = 0; i < sizeof(handoff->reserved); i++) {
        if (handoff->reserved[i] != 0) return SEMANTIC_E_RESERVATION;
    }

    return SEMANTIC_OK;
}

int elpis_write_topology_handoff(const char *path,
    const elpis_semantic_topology_handoff_v1 *handoff) {
    if (!path || !handoff) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, handoff, sizeof(*handoff));
    if ((size_t)w != sizeof(*handoff)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd);
    close(fd);
    return SEMANTIC_OK;
}

int elpis_read_topology_handoff(const char *path,
    elpis_semantic_topology_handoff_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    if ((size_t)r != sizeof(*out)) { close(fd); return SEMANTIC_E_IO; }
    close(fd);
    return elpis_topology_handoff_validate(out);
}
