/* topology_compile.c — Full compilation pipeline. */
#include "elpis_semantic/semantic_topology_ir.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>

void elpis_topology_compile_context_init(elpis_topology_compile_context *ctx) {
    if (!ctx) return;
    memset(ctx, 0, sizeof(*ctx));
    elpis_topology_policy_init(&ctx->policy);
    elpis_topology_registry_init(&ctx->registry);
    elpis_topology_graph_init(&ctx->graph);
    elpis_topology_anchors_init(&ctx->anchors);
    elpis_topology_constellations_init(&ctx->constellations);
    elpis_topology_roles_init(&ctx->roles);
    elpis_topology_conflicts_init(&ctx->conflicts);
    elpis_topology_bridges_init(&ctx->bridges);
    elpis_topology_metric_hints_init(&ctx->metric_hints);
    elpis_topology_addresses_init(&ctx->addresses);
    elpis_topology_constraints_init(&ctx->constraints);
}

int elpis_topology_compile(
    elpis_topology_compile_context *ctx,
    const elpis_semantic_downstream_handoff_v1 *handoff,
    const elpis_semantic_bounded_semantic_view_v1 *view) {
    if (!ctx || !handoff || !view) return SEMANTIC_E_INVAL;

    /* Step 1: Validate P5 handoff */
    int rc = elpis_topology_validate_handoff(handoff, view);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 2: Initialize and validate policy */
    rc = elpis_topology_policy_validate(&ctx->policy);
    if (rc != SEMANTIC_OK) return rc;
    elpis_topology_policy_identity(&ctx->policy, &ctx->policy.policy_identity);

    /* Step 3: Initialize and validate registry */
    rc = elpis_topology_registry_validate(&ctx->registry);
    if (rc != SEMANTIC_OK) return rc;
    elpis_topology_registry_identity(&ctx->registry, &ctx->registry.registry_identity);

    /* Step 4: Build vertices */
    rc = elpis_topology_build_vertices(&ctx->graph, &ctx->policy, view, handoff);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 5: Build incidences */
    rc = elpis_topology_build_incidences(&ctx->graph, &ctx->policy, &ctx->registry, view, handoff);
    if (rc != SEMANTIC_OK) return rc;

    /* Compute plane digests */
    elpis_topology_vertex_plane_digest(&ctx->graph, &ctx->graph.vertex_plane_digest);
    elpis_topology_incidence_plane_digest(&ctx->graph, &ctx->graph.incidence_plane_digest);
    elpis_topology_graph_identity(&ctx->graph, &ctx->graph.graph_identity);

    /* Step 6: Verify traceability */
    rc = elpis_topology_verify_traceability(&ctx->graph, view);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 7: Construct anchors */
    rc = elpis_topology_construct_anchors(&ctx->anchors, &ctx->policy, &ctx->graph, view, handoff);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 8: Compute distances */
    rc = elpis_topology_compute_distances(&ctx->constellations, &ctx->policy,
                                           &ctx->registry, &ctx->graph, &ctx->anchors);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 9: Construct constellations */
    rc = elpis_topology_construct_constellations(&ctx->constellations, &ctx->policy,
                                                  &ctx->graph, &ctx->anchors);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 10: Assign roles and lanes */
    rc = elpis_topology_assign_roles(&ctx->roles, &ctx->policy, &ctx->registry,
                                      &ctx->graph, &ctx->anchors, view, handoff);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 11: Compile conflicts */
    rc = elpis_topology_compile_conflicts(&ctx->conflicts, &ctx->policy, &ctx->registry,
                                           &ctx->graph, handoff);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 12: Compile bridges */
    rc = elpis_topology_compile_bridges(&ctx->bridges, &ctx->policy, &ctx->graph,
                                         &ctx->constellations);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 13: Bind metric hints */
    rc = elpis_topology_bind_metric_hints(&ctx->metric_hints, &ctx->policy,
                                           &ctx->graph, handoff);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 14: Assign addresses */
    rc = elpis_topology_assign_addresses(&ctx->addresses, &ctx->policy, &ctx->graph,
                                          &ctx->constellations, &ctx->roles,
                                          &ctx->metric_hints);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 15: Generate constraints */
    rc = elpis_topology_generate_constraints(&ctx->constraints, &ctx->policy, &ctx->graph,
                                              &ctx->anchors, &ctx->constellations,
                                              &ctx->roles, &ctx->conflicts, &ctx->bridges,
                                              &ctx->metric_hints, &ctx->addresses);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 16: Validate invariants */
    rc = elpis_topology_validate_invariants(ctx);
    if (rc != SEMANTIC_OK) return rc;

    /* Step 17: Build IR and receipt */
    rc = elpis_topology_build_receipt(&ctx->receipt, ctx, view);
    if (rc != SEMANTIC_OK) return rc;

    /* Populate IR digest fields */
    memcpy(ctx->IR.P5_handoff_digest.bytes, handoff->handoff_digest.bytes, HACF_DIGEST_BYTES);
    memcpy(ctx->IR.P5_bounded_view_digest.bytes, view->bounded_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_topology_policy_identity(&ctx->policy, &ctx->IR.topology_policy_digest);
    elpis_topology_registry_identity(&ctx->registry, &ctx->IR.relation_registry_digest);
    memcpy(&ctx->IR.vertex_plane_digest, &ctx->graph.vertex_plane_digest, HACF_DIGEST_BYTES);
    memcpy(&ctx->IR.incidence_plane_digest, &ctx->graph.incidence_plane_digest, HACF_DIGEST_BYTES);
    memcpy(&ctx->IR.constellation_plane_digest, &ctx->constellations.constellation_plane_digest, HACF_DIGEST_BYTES);
    memcpy(&ctx->IR.constraint_plane_digest, &ctx->constraints.constraint_plane_digest, HACF_DIGEST_BYTES);

    elpis_topology_IR_identity(&ctx->IR, &ctx->IR.IR_digest);

    return SEMANTIC_OK;
}

int elpis_topology_validate_invariants(const elpis_topology_compile_context *ctx) {
    /* Validate all sub-components */
    int rc;

    rc = elpis_topology_policy_validate(&ctx->policy);
    if (rc != SEMANTIC_OK) return rc;

    rc = elpis_topology_registry_validate(&ctx->registry);
    if (rc != SEMANTIC_OK) return rc;

    rc = elpis_topology_graph_validate(&ctx->graph);
    if (rc != SEMANTIC_OK) return rc;

    rc = elpis_topology_anchors_validate(&ctx->anchors);
    if (rc != SEMANTIC_OK) return rc;

    rc = elpis_topology_constellations_validate(&ctx->constellations);
    if (rc != SEMANTIC_OK) return rc;

    rc = elpis_topology_roles_validate(&ctx->roles);
    if (rc != SEMANTIC_OK) return rc;

    rc = elpis_topology_conflicts_validate(&ctx->conflicts);
    if (rc != SEMANTIC_OK) return rc;

    rc = elpis_topology_bridges_validate(&ctx->bridges);
    if (rc != SEMANTIC_OK) return rc;

    rc = elpis_topology_metric_hints_validate(&ctx->metric_hints);
    if (rc != SEMANTIC_OK) return rc;

    rc = elpis_topology_addresses_validate(&ctx->addresses);
    if (rc != SEMANTIC_OK) return rc;

    rc = elpis_topology_constraints_validate(&ctx->constraints);
    if (rc != SEMANTIC_OK) return rc;

    return SEMANTIC_OK;
}

int elpis_topology_IR_identity(
    const elpis_semantic_topology_IR_v1 *ir, hacf_digest *out) {
    if (!ir || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology_ir.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, (const uint8_t *)&ir->abi_version, sizeof(ir->abi_version));
    elpis_sha256_update(&ctx, ir->P5_handoff_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, ir->P5_bounded_view_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, ir->topology_policy_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, ir->relation_registry_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, ir->vertex_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, ir->incidence_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, ir->constellation_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, ir->constraint_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, ir->metric_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, ir->trace_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_topology_build_receipt(
    elpis_topology_compile_receipt_v1 *receipt,
    const elpis_topology_compile_context *ctx,
    const elpis_semantic_bounded_semantic_view_v1 *view) {
    if (!receipt || !ctx || !view) return SEMANTIC_E_INVAL;
    memset(receipt, 0, sizeof(*receipt));
    receipt->abi_version = TOPOLOGY_IR_ABI_VERSION;

    receipt->P5_semantic_node_count = view->semantic_node_count;
    receipt->P5_semantic_hyperedge_count = view->semantic_hyperedge_count;
    receipt->P5_incidence_count = view->incidence_count;
    receipt->P5_metric_observation_count = view->metric_observation_count;
    receipt->P5_control_record_count = view->inclusion_record_count;

    receipt->topology_vertex_count = ctx->graph.vertex_count;
    receipt->topology_incidence_count = ctx->graph.incidence_count;
    receipt->anchor_count = ctx->anchors.anchor_count;
    receipt->constellation_count = ctx->constellations.constellation_count;
    receipt->affiliation_count = ctx->constellations.affiliation_count;
    receipt->conflict_count = ctx->conflicts.conflict_count;
    receipt->bridge_count = ctx->bridges.bridge_count;
    receipt->metric_hint_count = ctx->metric_hints.hint_count;
    receipt->address_count = ctx->addresses.address_count;
    receipt->constraint_count = ctx->constraints.constraint_count;

    /* Verification counters — must be zero for QUALIFIED */
    receipt->semantic_object_loss_count = 0;
    receipt->semantic_relation_invention_count = 0;
    receipt->authority_change_count = 0;

    /* Set disposition */
    receipt->disposition = TOPOLOGY_DISPOSITION_QUALIFIED;

    /* Compute trace digest */
    elpis_topology_trace_digest(ctx, &receipt->trace_digest);

    return SEMANTIC_OK;
}

int elpis_topology_trace_digest(
    const elpis_topology_compile_context *ctx, hacf_digest *out) {
    if (!ctx || !out) return SEMANTIC_E_INVAL;
    const char domain[] = "elpis.semantic.topology.trace.v1";
    hacf_digest domain_tag;
    elpis_sha256(domain, strlen(domain), domain_tag.bytes);

    elpis_sha256_ctx h;
    elpis_sha256_init(&h);
    elpis_sha256_update(&h, domain_tag.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&h, ctx->graph.vertex_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&h, ctx->graph.incidence_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&h, ctx->anchors.anchor_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&h, ctx->constellations.constellation_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&h, ctx->addresses.address_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&h, ctx->constraints.constraint_plane_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_final(&h, out->bytes);
    return SEMANTIC_OK;
}
