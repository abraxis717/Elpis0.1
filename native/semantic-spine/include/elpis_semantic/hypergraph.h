/* elpis_semantic/hypergraph.h — Immutable typed-incidence semantic hypergraph builder.
 *
 * Accepts semantic objects in arbitrary insertion order and produces canonical
 * output. Validates against the type registry.
 */
#ifndef ELPIS_SEMANTIC_HYPERGRAPH_H
#define ELPIS_SEMANTIC_HYPERGRAPH_H

#include "elpis_semantic/identity.h"
#include "elpis_semantic/type_registry.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SEMANTIC_MAX_NODES       10000u
#define SEMANTIC_MAX_ASSERTIONS  20000u
#define SEMANTIC_MAX_HYPEREDGES  10000u
#define SEMANTIC_MAX_INCIDENCES  20000u

/* Builder status codes (additive on identity errors). */
#define SEMANTIC_BUILDER_OK              0
#define SEMANTIC_BUILDER_E_INVAL        -10
#define SEMANTIC_BUILDER_E_NOMEM        -11
#define SEMANTIC_BUILDER_E_DUPLICATE    -12
#define SEMANTIC_BUILDER_E_CONFLICT     -13
#define SEMANTIC_BUILDER_E_MISSING_NODE -14
#define SEMANTIC_BUILDER_E_MISSING_EDGE -15
#define SEMANTIC_BUILDER_E_PARTICIPANT  -16
#define SEMANTIC_BUILDER_E_CARDINALITY  -17
#define SEMANTIC_BUILDER_E_ORDINAL      -18
#define SEMANTIC_BUILDER_E_ROLE         -19
#define SEMANTIC_BUILDER_E_ZERO_PART    -20
#define SEMANTIC_BUILDER_E_IDENTITY     -21
#define SEMANTIC_BUILDER_E_RESERVED     -22
#define SEMANTIC_BUILDER_E_AUTHORITY    -23

/* Builder holds uncommitted records. */
typedef struct semantic_hypergraph_builder semantic_hypergraph_builder;

/* Create builder against a sealed type registry. */
semantic_hypergraph_builder *semantic_builder_create(const semantic_type_registry *reg);
void semantic_builder_destroy(semantic_hypergraph_builder *b);

/* Add records. Returns SEMANTIC_BUILDER_OK or error.
 * Exact duplicates collapse silently. Conflicting duplicates (same identity,
 * different payload) are rejected. */
int semantic_builder_add_node(semantic_hypergraph_builder *b,
                               const elpis_semantic_node_v1 *node);
int semantic_builder_add_assertion(semantic_hypergraph_builder *b,
                                    const elpis_semantic_assertion_v1 *assertion);
int semantic_builder_add_hyperedge(semantic_hypergraph_builder *b,
                                    const elpis_semantic_hyperedge_v1 *edge);
int semantic_builder_add_incidence(semantic_hypergraph_builder *b,
                                    const elpis_semantic_incidence_v1 *incidence);

/* Record counts. */
uint32_t semantic_builder_node_count(const semantic_hypergraph_builder *b);
uint32_t semantic_builder_assertion_count(const semantic_hypergraph_builder *b);
uint32_t semantic_builder_hyperedge_count(const semantic_hypergraph_builder *b);
uint32_t semantic_builder_incidence_count(const semantic_hypergraph_builder *b);

/* ───────────────────────────────────────────────────────────────────── */
/* Canonical output                                                      */
/* ───────────────────────────────────────────────────────────────────── */

/* Canonical record order:
 * 1. semantic nodes by node digest
 * 2. node assertions by (asserted_object_digest, provenance, authority, flags)
 * 3. hyperedges by hyperedge digest
 * 4. hyperedge assertions by (asserted_object_digest, provenance, authority, flags)
 * 5. incidences by (hyperedge_digest, role, ordinal, node_digest, flags)
 *
 * The builder stores records in canonical order — no re-sorting needed on output.
 */

/* Access canonical records by index. Returns NULL if out of range. */
const elpis_semantic_node_v1 *semantic_builder_get_node(const semantic_hypergraph_builder *b, uint32_t index);
const elpis_semantic_assertion_v1 *semantic_builder_get_assertion(const semantic_hypergraph_builder *b, uint32_t index);
const elpis_semantic_hyperedge_v1 *semantic_builder_get_hyperedge(const semantic_hypergraph_builder *b, uint32_t index);
const elpis_semantic_incidence_v1 *semantic_builder_get_incidence(const semantic_hypergraph_builder *b, uint32_t index);

/* Check if a node exists in the builder by digest. Returns 1 if found, 0 if not. */
int semantic_builder_has_node(const semantic_hypergraph_builder *b, const hacf_digest *digest);

/* Check if a hyperedge exists in the builder by digest. Returns 1 if found, 0 if not. */
int semantic_builder_has_hyperedge(const semantic_hypergraph_builder *b, const hacf_digest *digest);

#ifdef __cplusplus
}
#endif
#endif
