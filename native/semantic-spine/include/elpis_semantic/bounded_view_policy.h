/* elpis_semantic/bounded_view_policy.h — Bounded-view policy for P5.
 *
 * Defines hard capacity limits and closure rules for constructing a
 * bounded semantic view. These are bounded-view policy limits, not
 * Grid81 dimensions.
 *
 * Identity domain: "elpis.semantic.bounded_view_policy.v1"
 */
#ifndef ELPIS_SEMANTIC_BOUNDED_VIEW_POLICY_H
#define ELPIS_SEMANTIC_BOUNDED_VIEW_POLICY_H

#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BOUNDED_VIEW_POLICY_ABI_VERSION 1u

/* ──────────────────────────────────────────────────────────────────── */
/* Closure policy                                                        */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum bounded_view_closure_policy {
    CLOSURE_FAIL_CLOSED        = 0,  /* mandatory overflow → BLOCKED_BY_CAPACITY */
    CLOSURE_DETERMINISTIC_OMIT = 1   /* optional overflow → omit lower-ranked */
} bounded_view_closure_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* Overflow behavior                                                     */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum bounded_view_overflow_behavior {
    OVERFLOW_FAIL_CLOSED       = 0,  /* mandatory overflow → fail closed */
    OVERFLOW_OMIT_OPTIONAL     = 1   /* optional overflow → deterministic omission */
} bounded_view_overflow_behavior;

/* ──────────────────────────────────────────────────────────────────── */
/* Policy flags                                                          */
/* ──────────────────────────────────────────────────────────────────── */

#define BOUNDED_VIEW_FLAG_NONE                  0u
#define BOUNDED_VIEW_ALLOW_METRIC_SUPPLEMENT    0x01u
#define BOUNDED_VIEW_ALLOW_DIAGNOSTIC           0x02u
#define BOUNDED_VIEW_ALLOW_TRANSPORT_WITNESS    0x04u
#define BOUNDED_VIEW_REQUIRE_CONFLICT_CLOSURE   0x08u
#define BOUNDED_VIEW_REQUIRE_PROVENANCE_CLOSURE 0x10u
#define BOUNDED_VIEW_FLAG_MASK                  0xFFu

/* ──────────────────────────────────────────────────────────────────── */
/* Bounded view policy                                                   */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_bounded_view_policy_v1 {
    uint32_t                abi_version;

    /* Hard capacity limits */
    uint32_t                maximum_semantic_nodes;
    uint32_t                maximum_semantic_hyperedges;
    uint32_t                maximum_incidences;
    uint32_t                maximum_assertions;
    uint32_t                maximum_source_spans;
    uint32_t                maximum_transport_references;
    uint32_t                maximum_embedding_references;
    uint32_t                maximum_metric_observations;

    /* Traversal limits */
    uint32_t                maximum_graph_hops;
    uint32_t                maximum_metric_neighbors_per_seed;

    /* Authority floors */
    uint32_t                minimum_assertion_authority;
    uint32_t                minimum_source_authority;

    /* Type filters */
    hacf_digest             allowed_node_type_registry_digest;
    hacf_digest             allowed_hyperedge_type_registry_digest;

    /* Relation and profile allowlists */
    hacf_digest             semantic_relation_allowlist_digest;
    hacf_digest             transport_relation_allowlist_digest;
    hacf_digest             metric_profile_allowlist_digest;

    /* Closure policies */
    uint32_t                mandatory_seed_policy;        /* bounded_view_closure_policy */
    uint32_t                conflict_closure_policy;      /* bounded_view_closure_policy */
    uint32_t                provenance_closure_policy;    /* bounded_view_closure_policy */
    uint32_t                scope_closure_policy;         /* bounded_view_closure_policy */
    uint32_t                qualifier_closure_policy;     /* bounded_view_closure_policy */

    /* Inclusion policies */
    uint32_t                transport_inclusion_policy;   /* bounded_view_overflow_behavior */
    uint32_t                metric_supplement_policy;     /* bounded_view_overflow_behavior */

    /* Overflow behavior */
    uint32_t                overflow_behavior;            /* bounded_view_overflow_behavior */

    /* Omission receipt policy */
    uint32_t                omission_receipt_policy;      /* bounded_view_closure_policy */

    /* Identity */
    hacf_digest             policy_identity;
    uint32_t                policy_flags;

    uint8_t                 reserved[64];
} elpis_semantic_bounded_view_policy_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Default P5 v1 policy construction                                     */
/* ──────────────────────────────────────────────────────────────────── */

/* Construct default P5 v1 bounded-view policy:
 *   max_nodes: 256, max_hyperedges: 512, max_incidences: 2048
 *   max_assertions: 1024, max_spans: 256, max_transport: 256
 *   max_embedding: 256, max_metric: 512
 *   max_graph_hops: 2, max_metric_neighbors: 8
 *   overflow: FAIL_CLOSED for mandatory, OMIT_OPTIONAL for optional
 * Returns SEMANTIC_OK on success. */
int elpis_bounded_view_policy_default(
    elpis_semantic_bounded_view_policy_v1 *policy);

/* Zero-initialize. Sets abi_version. */
void elpis_bounded_view_policy_init(
    elpis_semantic_bounded_view_policy_v1 *policy);

/* Compute policy identity. Domain: "elpis.semantic.bounded_view_policy.v1" */
int elpis_bounded_view_policy_identity(
    const elpis_semantic_bounded_view_policy_v1 *policy, hacf_digest *out);

/* Validate: known ABI, zero reserved, positive limits, valid enums. */
int elpis_bounded_view_policy_validate(
    const elpis_semantic_bounded_view_policy_v1 *policy);

/* Persistence */
int elpis_write_bounded_view_policy(const char *path,
                                     const elpis_semantic_bounded_view_policy_v1 *policy);
int elpis_read_bounded_view_policy(const char *path,
                                    elpis_semantic_bounded_view_policy_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
