/* elpis_semantic/snapshot.h — Append-only snapshot manifests.
 *
 * A snapshot manifest binds an ordered chain of segments to a resulting HACF
 * graph snapshot. Snapshots are append-only — no physical deletion. Future
 * correction or retraction is expressed by semantic records in later segments.
 */
#ifndef ELPIS_SEMANTIC_SNAPSHOT_H
#define ELPIS_SEMANTIC_SNAPSHOT_H

#include "elpis_semantic/segment.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SEMANTIC_SNAPSHOT_ABI_VERSION 1u
#define SEMANTIC_MAX_SEGMENTS 4096u

/* ───────────────────────────────────────────────────────────────────── */
/* Snapshot manifest                                                     */
/* ───────────────────────────────────────────────────────────────────── */

typedef struct semantic_snapshot_manifest {
    uint32_t              abi_version;
    hacf_digest           type_registry_digest;
    hacf_digest           genesis_identity;
    hacf_digest           prior_manifest_digest; /* all-zero for first manifest */
    hacf_digest           segment_digests[SEMANTIC_MAX_SEGMENTS];
    uint32_t              segment_count;
    hacf_digest           hacf_graph_snapshot_digest;
    uint32_t              unique_node_count;
    uint32_t              unique_hyperedge_count;
    uint32_t              assertion_count;
    uint32_t              incidence_count;
    hacf_digest           manifest_digest;
    hacf_digest           hacf_package_digest;
    uint8_t               reserved[32];
} semantic_snapshot_manifest;

/* ───────────────────────────────────────────────────────────────────── */
/* Manifest operations                                                   */
/* ───────────────────────────────────────────────────────────────────── */

/* Create a new snapshot manifest. */
semantic_snapshot_manifest *semantic_snapshot_create(void);
void semantic_snapshot_destroy(semantic_snapshot_manifest *m);

/* Add a segment to the manifest (appends). Validates chain continuity:
 * - segment prior snapshot equals preceding result snapshot
 * - registry identity matches
 * - no duplicate segments (unless schema permits)
 * Returns SEMANTIC_OK or error. */
int semantic_snapshot_add_segment(semantic_snapshot_manifest *m,
                                   const semantic_segment_record *segment);

/* Finalize and compute manifest digest. Domain: "elpis.semantic.snapshot.v1" */
int semantic_snapshot_finalize(semantic_snapshot_manifest *m);

/* Validate the entire chain: continuity, uniqueness, registry consistency.
 * Returns SEMANTIC_OK or specific error. */
int semantic_snapshot_validate(const semantic_snapshot_manifest *m);

/* Write manifest to filesystem atomically. */
int semantic_snapshot_write(const semantic_snapshot_manifest *m,
                             const char *path,
                             char hex_out[65]);

/* Read and verify manifest. */
int semantic_snapshot_read(const char *path,
                            semantic_snapshot_manifest *m_out);

/* Get manifest digest. */
int semantic_snapshot_digest(const semantic_snapshot_manifest *m, hacf_digest *out);

#ifdef __cplusplus
}
#endif
#endif
