/* elpis_semantic/semantic_topology_ir.h — Immutable topology IR and compile receipt.
 *
 * Binds all P6 outputs into a single immutable topology intermediate
 * representation. Produces compile receipt with verification counters.
 *
 * Identity domain: "elpis.semantic.topology_ir.v1"
 */
#ifndef ELPIS_SEMANTIC_SEMANTIC_TOPOLOGY_IR_H
#define ELPIS_SEMANTIC_SEMANTIC_TOPOLOGY_IR_H

#include "elpis_semantic/topology_policy.h"
#include "elpis_semantic/topology_registry.h"
#include "elpis_semantic/topology_graph.h"
#include "elpis_semantic/topology_anchor.h"
#include "elpis_semantic/topology_constellation.h"
#include "elpis_semantic/topology_address.h"
#include "elpis_semantic/topology_constraint.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TOPOLOGY_IR_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Disposition                                                           */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum topology_compile_disposition {
    TOPOLOGY_DISPOSITION_QUALIFIED = 0,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_HANDOFF    = 1,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_REGISTRY   = 2,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_INPUT      = 3,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_MAPPING    = 4,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_ANCHORS    = 5,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_DISTANCE   = 6,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_AFFILIATION= 7,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_CONFLICT   = 8,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_ADDRESS    = 9,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_CONSTRAINT = 10,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_INVARIANT  = 11,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_HANDOFF_ABI= 12,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_STORAGE    = 13,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_DETERMINISM= 14,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_SANITIZER  = 15,
    TOPOLOGY_DISPOSITION_BLOCKED_BY_TEST       = 16,
} topology_compile_disposition;

/* ──────────────────────────────────────────────────────────────────── */
/* Compile receipt — immutable record of compilation                    */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_topology_compile_receipt_v1 {
    uint32_t                          abi_version;
    topology_compile_disposition      disposition;

    /* Input counts */
    uint32_t                          P5_semantic_node_count;
    uint32_t                          P5_semantic_hyperedge_count;
    uint32_t                          P5_incidence_count;
    uint32_t                          P5_metric_observation_count;
    uint32_t                          P5_control_record_count;

    /* Output counts */
    uint32_t                          topology_vertex_count;
    uint32_t                          topology_incidence_count;
    uint32_t                          anchor_count;
    uint32_t                          constellation_count;
    uint32_t                          affiliation_count;
    uint32_t                          conflict_count;
    uint32_t                          bridge_count;
    uint32_t                          metric_hint_count;
    uint32_t                          address_count;
    uint32_t                          constraint_count;

    /* Verification counters — must all be zero for QUALIFIED */
    uint32_t                          semantic_object_loss_count;
    uint32_t                          semantic_relation_invention_count;
    uint32_t                          authority_change_count;

    /* Digests */
    hacf_digest                       topology_IR_digest;
    hacf_digest                       trace_digest;
    uint8_t                           reserved[64];
} elpis_topology_compile_receipt_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Topology IR — complete immutable binding                             */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_topology_IR_v1 {
    uint32_t                          abi_version;

    /* P5 handoff binding */
    hacf_digest                       P5_handoff_digest;
    hacf_digest                       P5_bounded_view_digest;

    /* Policy and registry */
    hacf_digest                       topology_policy_digest;
    hacf_digest                       relation_registry_digest;

    /* Ordered topology data (digests — actual data in separate plane files) */
    hacf_digest                       ordered_vertices_digest;
    hacf_digest                       ordered_incidences_digest;
    hacf_digest                       ordered_anchors_digest;
    hacf_digest                       ordered_constellations_digest;
    hacf_digest                       ordered_affiliations_digest;
    hacf_digest                       ordered_conflicts_digest;
    hacf_digest                       ordered_bridges_digest;
    hacf_digest                       ordered_metric_hints_digest;
    hacf_digest                       ordered_addresses_digest;
    hacf_digest                       ordered_constraints_digest;

    /* Plane digests */
    hacf_digest                       vertex_plane_digest;
    hacf_digest                       incidence_plane_digest;
    hacf_digest                       constellation_plane_digest;
    hacf_digest                       constraint_plane_digest;
    hacf_digest                       metric_plane_digest;
    hacf_digest                       trace_plane_digest;

    /* IR and package identities */
    hacf_digest                       IR_digest;
    hacf_digest                       HACF_package_digest;
    uint8_t                           reserved[64];
} elpis_semantic_topology_IR_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Compile context — mutable workspace for compilation                  */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_topology_compile_context {
    elpis_semantic_topology_policy_v1            policy;
    elpis_semantic_topology_relation_registry_v1 registry;
    elpis_semantic_topology_graph_v1             graph;
    elpis_semantic_topology_anchors_v1           anchors;
    elpis_semantic_topology_constellations_v1    constellations;
    elpis_semantic_topology_roles_v1             roles;
    elpis_semantic_topology_conflicts_v1         conflicts;
    elpis_semantic_topology_bridges_v1           bridges;
    elpis_semantic_topology_metric_hints_v1      metric_hints;
    elpis_semantic_topology_addresses_v1         addresses;
    elpis_semantic_topology_constraints_v1       constraints;
    elpis_semantic_topology_IR_v1                IR;
    elpis_topology_compile_receipt_v1            receipt;
} elpis_topology_compile_context;

/* ──────────────────────────────────────────────────────────────────── */
/* Full compilation pipeline                                             */
/* ──────────────────────────────────────────────────────────────────── */

/* Initialize compile context with all defaults. */
void elpis_topology_compile_context_init(elpis_topology_compile_context *ctx);

/* Execute full compilation sequence. Returns SEMANTIC_OK or error.
 * Sequence: validate -> vertices -> incidences -> registry -> anchors ->
 * distances -> constellations -> roles -> conflicts -> bridges ->
 * metric hints -> addresses -> constraints -> invariants -> digests. */
int elpis_topology_compile(
    elpis_topology_compile_context *ctx,
    const elpis_semantic_downstream_handoff_v1 *handoff,
    const elpis_semantic_bounded_semantic_view_v1 *view);

/* Compute IR identity. Domain: "elpis.semantic.topology_ir.v1" */
int elpis_topology_IR_identity(
    const elpis_semantic_topology_IR_v1 *ir, hacf_digest *out);

/* Validate all invariants: traceability, capacity, no pairwise invention,
 * no Grid81 coupling, no authority changes. */
int elpis_topology_validate_invariants(
    const elpis_topology_compile_context *ctx);

/* Build compile receipt from completed context. */
int elpis_topology_build_receipt(
    elpis_topology_compile_receipt_v1 *receipt,
    const elpis_topology_compile_context *ctx,
    const elpis_semantic_bounded_semantic_view_v1 *view);

/* Compute trace digest covering all topology outputs. */
int elpis_topology_trace_digest(
    const elpis_topology_compile_context *ctx, hacf_digest *out);

/* Persistence for IR and receipt */
int elpis_write_topology_IR(const char *path,
    const elpis_semantic_topology_IR_v1 *ir);
int elpis_read_topology_IR(const char *path,
    elpis_semantic_topology_IR_v1 *out);
int elpis_write_compile_receipt(const char *path,
    const elpis_topology_compile_receipt_v1 *receipt);
int elpis_read_compile_receipt(const char *path,
    elpis_topology_compile_receipt_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
