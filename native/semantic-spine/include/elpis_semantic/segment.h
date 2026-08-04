/* elpis_semantic/segment.h — Immutable semantic segments with HACF mapping.
 *
 * A segment binds a set of canonical semantic records to a HACF graph delta,
 * producing a verifiable chain of immutable snapshots. Genesis segment uses
 * a defined genesis identity rather than an unexplained all-zero prior.
 *
 * Publication uses atomic no-replace with fsync. Pre-existing destination is never replaced.
 */
#ifndef ELPIS_SEMANTIC_SEGMENT_H
#define ELPIS_SEMANTIC_SEGMENT_H

#include "elpis_semantic/hypergraph.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SEMANTIC_SEGMENT_ABI_VERSION 1u

/* ───────────────────────────────────────────────────────────────────── */
/* Segment record                                                        */
/* ───────────────────────────────────────────────────────────────────── */

typedef struct semantic_segment_record {
    uint32_t              abi_version;
    hacf_digest           type_registry_digest;
    hacf_digest           prior_snapshot_digest;
    hacf_digest           segment_identity;     /* SHA-256 of canonical payload */
    uint32_t              node_count;
    uint32_t              assertion_count;
    uint32_t              hyperedge_count;
    uint32_t              incidence_count;
    uint32_t              hacf_op_count;
    hacf_digest           hacf_delta_digest;
    hacf_digest           hacf_next_snapshot;
    hacf_digest           hacf_package_digest;
    uint8_t               reserved[64];         /* must be zero */
} semantic_segment_record;

/* ───────────────────────────────────────────────────────────────────── */
/* Genesis identity                                                      */
/* ───────────────────────────────────────────────────────────────────── */

/* Compute genesis snapshot identity: SHA-256("elpis.semantic.genesis.v1" || type_registry_digest).
 * This is the prior_snapshot_digest for the first segment. */
int semantic_genesis_identity(const hacf_digest *type_registry_digest, hacf_digest *genesis_out);

/* ───────────────────────────────────────────────────────────────────── */
/* Segment writer                                                        */
/* ───────────────────────────────────────────────────────────────────── */

/* Build a segment from a canonical builder. The builder's records must already
 * be in canonical order (which they are by construction).
 *
 * prior_snapshot: for genesis segments, pass the genesis identity.
 * Returns SEMANTIC_OK on success; error codes from builder/HACF otherwise. */
int semantic_segment_build(const semantic_hypergraph_builder *builder,
                            const semantic_type_registry *registry,
                            const hacf_digest *prior_snapshot,
                            semantic_segment_record *segment_out);

/* Write segment to filesystem path atomically: temp file → write → fsync →
 * rename (O_EXCL on destination) → directory fsync.
 * Returns SEMANTIC_OK or error. Pre-existing destination is never replaced. */
int semantic_segment_write(const semantic_segment_record *segment,
                            const semantic_hypergraph_builder *builder,
                            const char *path,
                            char segment_hex_out[65]);

/* ───────────────────────────────────────────────────────────────────── */
/* Segment reader                                                        */
/* ───────────────────────────────────────────────────────────────────── */

/* Read and verify a segment file. Recalculates all identities, rejects corruption.
 * Returns SEMANTIC_OK on success. */
int semantic_segment_read(const char *path,
                           semantic_segment_record *segment_out,
                           hacf_digest *segment_digest_out);

/* Validate segment identity: recalculates segment identity from builder content
 * and compares. Returns 1 if valid, 0 if corrupted. */
int semantic_segment_validate(const semantic_segment_record *segment,
                               const hacf_digest *expected_segment_digest);

/* Compute segment identity digest (SHA-256 of canonical serialized record).
 * Domain: "elpis.semantic.segment.v1" */
int semantic_segment_identity(const semantic_segment_record *segment, hacf_digest *out);

#ifdef __cplusplus
}
#endif
#endif
