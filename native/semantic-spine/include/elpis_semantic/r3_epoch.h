/* elpis_semantic/r3_epoch.h — R3 epoch binding for P3 retrieval bridge.
 *
 * Binds an exact R3 retrieval epoch: corpus, vector index, optional context
 * graph, hybrid policy. Provides drift detection — no automatic retry.
 *
 * Identity domain: "elpis.semantic.r3_epoch.v1"
 */
#ifndef ELPIS_SEMANTIC_R3_EPOCH_H
#define ELPIS_SEMANTIC_R3_EPOCH_H

#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define R3_EPOCH_ABI_VERSION 1u

/* Forward declarations from R3 public ABI */
struct elpis_corpus;
struct elpis_vector_index;
struct elpis_context_graph;
struct elpis_hybrid_policy;
typedef struct elpis_corpus elpis_corpus;
typedef struct elpis_vector_index elpis_vector_index;
typedef struct elpis_context_graph elpis_context_graph;
typedef struct elpis_hybrid_policy elpis_hybrid_policy;

/* ──────────────────────────────────────────────────────────────────── */
/* R3 epoch binding record */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_r3_epoch_binding_v1 {
    uint32_t                    abi_version;
    char                        corpus_manifest_digest[65];
    char                        vector_index_manifest_digest[65];
    char                        vector_index_profile_digest[65];
    char                        index_corpus_binding[65]; /* corpus digest from index */
    char                        context_graph_digest[65]; /* all-zero if no graph */
    char                        hybrid_policy_digest[65];
    uint32_t                    r3_abi_version;
    hacf_digest                 bridge_policy_digest;
    hacf_digest                 epoch_binding_digest;
    uint8_t                     reserved[32];
} elpis_r3_epoch_binding_v1;

/* Create an epoch binding from live R3 handles. Returns SEMANTIC_OK or error.
 * Validates:
 *   - nonzero corpus manifest digest
 *   - nonzero index manifest digest
 *   - index bound to the same corpus (index_corpus_binding == corpus_manifest_digest)
 *   - profile digest nonzero
 *   - context graph digest set if graph present, all-zero if absent
 *   - valid hybrid policy digest
 *   - R3 ABI version matches ELPIS_HYBRID_ABI_VERSION */
int elpis_r3_epoch_binding_create(
    elpis_r3_epoch_binding_v1 *binding,
    elpis_corpus *corpus,
    elpis_vector_index *index,
    const elpis_context_graph *graph,
    const elpis_hybrid_policy *policy,
    const hacf_digest *bridge_policy);

/* Zero-initialize an epoch binding. Sets abi_version. */
void elpis_r3_epoch_binding_init(elpis_r3_epoch_binding_v1 *binding);

/* Compute epoch binding identity digest.
 * Domain: "elpis.semantic.r3_epoch.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || corpus_manifest_digest(64 hex)
 *             || vector_index_manifest_digest(64 hex)
 *             || vector_index_profile_digest(64 hex)
 *             || index_corpus_binding(64 hex)
 *             || context_graph_digest(64 hex)
 *             || hybrid_policy_digest(64 hex)
 *             || r3_abi_version(4 BE)
 *             || bridge_policy_digest(32). */
int elpis_r3_epoch_binding_digest(
    const elpis_r3_epoch_binding_v1 *binding, hacf_digest *out);

/* Validate: known ABI, zero reserved, nonzero required digests,
 * corpus == index_corpus_binding. */
int elpis_r3_epoch_binding_validate(
    const elpis_r3_epoch_binding_v1 *binding);

/* Check for drift: re-query corpus/index manifests and compare.
 * Returns SEMANTIC_OK if no drift, or specific drift error. */
int elpis_r3_epoch_check_drift(
    const elpis_r3_epoch_binding_v1 *binding,
    elpis_corpus *corpus,
    elpis_vector_index *index);

/* Check for drift: re-query corpus/index manifests and compare.
 * Returns SEMANTIC_OK if no drift, SEMANTIC_E_DIGEST on drift. */
int elpis_r3_epoch_check_drift_post(
    const elpis_r3_epoch_binding_v1 *binding,
    elpis_corpus *corpus,
    elpis_vector_index *index);

#ifdef __cplusplus
}
#endif
#endif
