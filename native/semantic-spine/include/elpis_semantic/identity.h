/* elpis_semantic/identity.h — Semantic identity model for typed hypergraph core.
 *
 * Three distinct identity concepts:
 *   1. Semantic node identity  — stable semantic object
 *   2. Semantic hyperedge identity — typed N-ary relation instance
 *   3. Assertion identity    — provenance-bearing admission record
 *   4. Incidence identity    — hyperedge-to-participant binding
 *
 * All digests are 32 bytes (SHA-256). Hex boundaries use lowercase 64-char only.
 * No host padding, pointers, or timestamps enter identity digests.
 */
#ifndef ELPIS_SEMANTIC_IDENTITY_H
#define ELPIS_SEMANTIC_IDENTITY_H

#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ──────────────────────────────────────────────────────────────────── */
/* Status codes — shared across all semantic headers                   */
/* ──────────────────────────────────────────────────────────────────── */

#define SEMANTIC_OK                  0
#define SEMANTIC_E_INVAL            -1
#define SEMANTIC_E_NOMEM            -2
#define SEMANTIC_E_NOTFOUND         -3
#define SEMANTIC_E_DUPLICATE        -4
#define SEMANTIC_E_NAMESPACE_COLLISION -5
#define SEMANTIC_E_CARDINALITY      -6
#define SEMANTIC_E_RESERVATION      -7
#define SEMANTIC_E_REGISTRY_FULL    -8
#define SEMANTIC_E_IO               -9
#define SEMANTIC_E_DIGEST           -10
#define SEMANTIC_E_AUTHORITY        -11

#define SEMANTIC_ABI_VERSION 1u
#define SEMANTIC_DIGEST_BYTES HACF_DIGEST_BYTES

/* ───────────────────────────────────────────────────────────────────────── */
/* Semantic node identity                                                  */
/* ───────────────────────────────────────────────────────────────────────── */

/* Semantic flags — extendable; nonzero reserved bits are rejected. */
#define SEMANTIC_NODE_FLAG_NONE        0u
#define SEMANTIC_NODE_FLAG_EXTERNAL    0x01u  /* originated outside this fabric */
#define SEMANTIC_NODE_FLAG_MASK        0x01u

/* Node types live in namespace 0x10000000 | id */
#define SEMANTIC_NODE_NAMESPACE  0x10000000u

typedef struct elpis_semantic_node_v1 {
    uint32_t  abi_version;
    uint32_t  node_type;           /* semantic node type ID (namespace-prefixed) */
    uint32_t  semantic_flags;
    hacf_digest payload_digest;    /* SHA-256 of the semantic payload */
    hacf_digest node_identity;     /* computed identity digest */
    uint8_t   reserved[48];        /* must be zero */
} elpis_semantic_node_v1;

/* Compute node identity digest. Domain: "elpis.semantic.node.v1"
 * Byte stream: domain_tag(len+bytes) || abi_version(4 BE) || node_type(4 BE)
 *             || semantic_flags(4 BE) || payload_digest(32). */
int elpis_semantic_node_identity(const elpis_semantic_node_v1 *node, hacf_digest *out);

/* Validate node fields: known ABI, type in node namespace, zero reserved, valid digest. */
int elpis_semantic_node_validate(const elpis_semantic_node_v1 *node);

/* ───────────────────────────────────────────────────────────────────────── */
/* Semantic hyperedge identity                                             */
/* ───────────────────────────────────────────────────────────────────────── */

#define SEMANTIC_HYPEREDGE_FLAG_NONE  0u
#define SEMANTIC_HYPEREDGE_FLAG_MASK  0x01u

/* Hyperedge types live in namespace 0x20000000 | id */
#define SEMANTIC_HYPEREDGE_NAMESPACE 0x20000000u

/* Participant flags */
#define SEMANTIC_PARTICIPANT_FLAG_NONE     0u
#define SEMANTIC_PARTICIPANT_FLAG_QUERY    0x01u  /* query-local overlay participant */
#define SEMANTIC_PARTICIPANT_FLAG_MASK     0x01u

typedef struct elpis_semantic_participant_descriptor {
    hacf_digest node_identity;    /* the participant node's identity digest */
    uint32_t    incidence_role;   /* incidence-role type ID (namespace-prefixed) */
    uint32_t    ordinal;
    uint32_t    participant_flags;
    uint8_t     reserved[32];     /* must be zero */
} elpis_semantic_participant_descriptor;

#define SEMANTIC_MAX_PARTICIPANTS 64u

typedef struct elpis_semantic_hyperedge_v1 {
    uint32_t                                abi_version;
    uint32_t                                hyperedge_type;  /* semantic hyperedge type ID */
    uint32_t                                semantic_flags;
    hacf_digest                             payload_digest;   /* optional; may be zero */
    uint32_t                                participant_count;
    elpis_semantic_participant_descriptor   participants[SEMANTIC_MAX_PARTICIPANTS];
    hacf_digest                             hyperedge_identity; /* computed identity digest */
    uint8_t                                 reserved[32];     /* must be zero */
} elpis_semantic_hyperedge_v1;

/* Compute hyperedge identity. Domain: "elpis.semantic.hyperedge.v1"
 * Byte stream: domain_tag || abi_version(4 BE) || hyperedge_type(4 BE)
 *             || semantic_flags(4 BE) || payload_digest(32)
 *             || participant_count(4 BE) || for each sorted participant:
 *             node_identity(32) || incidence_role(4 BE) || ordinal(4 BE) || participant_flags(4 BE).
 *
 * Participants are sorted canonically by: role, ordinal, node_digest, flags. */
int elpis_semantic_hyperedge_identity(const elpis_semantic_hyperedge_v1 *edge, hacf_digest *out);

/* Validate hyperedge fields. */
int elpis_semantic_hyperedge_validate(const elpis_semantic_hyperedge_v1 *edge);

/* Canonical sort of participants in-place. Returns 0 on success. */
int elpis_semantic_canonicalize_participants(elpis_semantic_participant_descriptor *parts, uint32_t count);

/* ───────────────────────────────────────────────────────────────────────── */
/* Assertion identity                                                      */
/* ───────────────────────────────────────────────────────────────────────── */

typedef enum semantic_asserted_object_kind {
    SEMANTIC_OBJECT_KIND_NODE      = 1u,
    SEMANTIC_OBJECT_KIND_HYPEREDGE = 2u
} semantic_asserted_object_kind;

#define SEMANTIC_ASSERTION_FLAG_NONE  0u
#define SEMANTIC_ASSERTION_FLAG_MASK  0x03u

typedef struct elpis_semantic_assertion_v1 {
    uint32_t                          abi_version;
    semantic_asserted_object_kind     asserted_object_kind;
    hacf_digest                       asserted_object_digest;
    hacf_digest                       provenance_digest;
    uint32_t                          authority;
    uint32_t                          assertion_flags;
    hacf_digest                       assertion_identity; /* computed identity digest */
    uint8_t                           reserved[32];       /* must be zero */
} elpis_semantic_assertion_v1;

/* Assertion identity. Domain: "elpis.semantic.assertion.v1"
 * Byte stream: domain_tag || abi_version(4 BE) || object_kind(4 BE)
 *             || asserted_object_digest(32) || provenance_digest(32)
 *             || authority(4 BE) || assertion_flags(4 BE). */
int elpis_semantic_assertion_identity(const elpis_semantic_assertion_v1 *assertion, hacf_digest *out);

/* Validate assertion fields. */
int elpis_semantic_assertion_validate(const elpis_semantic_assertion_v1 *assertion);

/* ───────────────────────────────────────────────────────────────────────── */
/* Incidence identity                                                      */
/* ───────────────────────────────────────────────────────────────────────── */

/* Incidence roles live in namespace 0x30000000 | id */
#define SEMANTIC_INCIDENCE_NAMESPACE 0x30000000u

#define SEMANTIC_INCIDENCE_FLAG_NONE  0u
#define SEMANTIC_INCIDENCE_FLAG_MASK  0x01u

typedef struct elpis_semantic_incidence_v1 {
    uint32_t        abi_version;
    hacf_digest     hyperedge_digest;
    hacf_digest     node_digest;
    uint32_t        incidence_role;
    uint32_t        ordinal;
    uint32_t        participant_flags;
    hacf_digest     incidence_identity; /* computed identity digest */
    uint8_t         reserved[32];       /* must be zero */
} elpis_semantic_incidence_v1;

/* Incidence identity. Domain: "elpis.semantic.incidence.v1"
 * Byte stream: domain_tag || abi_version(4 BE) || hyperedge_digest(32)
 *             || node_digest(32) || incidence_role(4 BE)
 *             || ordinal(4 BE) || participant_flags(4 BE). */
int elpis_semantic_incidence_identity(const elpis_semantic_incidence_v1 *incidence, hacf_digest *out);

/* Validate incidence fields. */
int elpis_semantic_incidence_validate(const elpis_semantic_incidence_v1 *incidence);

/* ───────────────────────────────────────────────────────────────────────── */
/* Comparison helpers                                                      */
/* ───────────────────────────────────────────────────────────────────────── */

/* Compare two node records by identity digest (for canonical ordering). */
int elpis_semantic_node_cmp(const elpis_semantic_node_v1 *a, const elpis_semantic_node_v1 *b);

/* Compare two assertions by (asserted_object_digest, provenance, authority, flags). */
int elpis_semantic_assertion_cmp(const elpis_semantic_assertion_v1 *a, const elpis_semantic_assertion_v1 *b);

/* Compare two hyperedges by identity digest. */
int elpis_semantic_hyperedge_cmp(const elpis_semantic_hyperedge_v1 *a, const elpis_semantic_hyperedge_v1 *b);

/* Compare two incidences by (hyperedge_digest, role, ordinal, node_digest, flags). */
int elpis_semantic_incidence_cmp(const elpis_semantic_incidence_v1 *a, const elpis_semantic_incidence_v1 *b);

/* Check if two assertions are exact duplicates (same identity). */
int elpis_semantic_assertion_is_duplicate(const elpis_semantic_assertion_v1 *a, const elpis_semantic_assertion_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
