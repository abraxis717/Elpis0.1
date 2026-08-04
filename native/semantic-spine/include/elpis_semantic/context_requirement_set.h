/* elpis_semantic/context_requirement_set.h — Collection of context requirements.
 *
 * A requirement set binds a group of context requirements to one composed view
 * (base snapshot + overlay + embedding collections). Requirements within a set
 * are stored in canonical order by identity digest. The set identity is
 * deterministic from the overlay/view targets and sorted requirement digests.
 *
 * Identity domain: "elpis.semantic.context_requirement_set.v1"
 */
#ifndef ELPIS_SEMANTIC_CONTEXT_REQUIREMENT_SET_H
#define ELPIS_SEMANTIC_CONTEXT_REQUIREMENT_SET_H

#include "elpis_semantic/context_requirement.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define CONTEXT_REQUIREMENT_SET_ABI_VERSION 1u
#define CONTEXT_MAX_REQUIREMENTS            256

/* ──────────────────────────────────────────────────────────────────── */
/* Requirement set record                                                */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_context_requirement_set_v1 {
    uint32_t                                abi_version;
    hacf_digest                             target_query_overlay_digest;
    hacf_digest                             target_composed_view_digest;
    uint32_t                                requirement_count;
    hacf_digest                             requirement_digests[CONTEXT_MAX_REQUIREMENTS];
    hacf_digest                             requirement_set_policy_digest;
    hacf_digest                             requirement_set_identity;
    uint8_t                                 reserved[32];
} elpis_semantic_context_requirement_set_v1;

/* ──────────────────────────────────────────────────────────────────── */
/* Validation result                                                     */
/* ──────────────────────────────────────────────────────────────────── */

typedef enum context_set_validation_result {
    SET_VALID                  = 0,
    SET_INVALID_ABI            = 1,
    SET_INVALID_TARGET         = 2,
    SET_INVALID_POLICY         = 3,
    SET_DUPLICATE_REQUIREMENT  = 4,
    SET_CONFLICTING_MANDATORY  = 5,
    SET_OVERLAY_MISMATCH       = 6,
    SET_COUNT_EXCEEDED         = 7
} context_set_validation_result;

/* ──────────────────────────────────────────────────────────────────── */
/* Requirement set operations                                            */
/* ──────────────────────────────────────────────────────────────────── */

/* Zero-initialize a requirement set. Sets abi_version. */
void elpis_context_requirement_set_init(
    elpis_semantic_context_requirement_set_v1 *set);

/* Add a requirement digest to the set (canonical order by digest).
 * Duplicate digests are silently collapsed.
 * Returns SEMANTIC_OK, SEMANTIC_E_INVAL (count exceeded), or SEMANTIC_E_DUPLICATE. */
int elpis_context_requirement_set_add(
    elpis_semantic_context_requirement_set_v1 *set,
    const hacf_digest *requirement_digest);

/* Compute requirement set identity. Domain: "elpis.semantic.context_requirement_set.v1"
 * Byte stream: domain_tag || abi_version(4 BE)
 *             || target_query_overlay_digest(32)
 *             || target_composed_view_digest(32)
 *             || requirement_count(4 BE)
 *             || for each requirement digest (canonical order): digest(32)
 *             || requirement_set_policy_digest(32). */
int elpis_context_requirement_set_identity(
    const elpis_semantic_context_requirement_set_v1 *set, hacf_digest *out);

/* Validate requirement set: known ABI, zero reserved, sorted requirement digests,
 * count within bounds, target digests non-zero.
 * Returns SET_VALID (0) or a context_set_validation_result error code. */
int elpis_context_requirement_set_validate(
    const elpis_semantic_context_requirement_set_v1 *set);

/* Sort requirement digests into canonical order (ascending lexicographic by
 * digest bytes). Idempotent. Returns SEMANTIC_OK or SEMANTIC_E_INVAL. */
int elpis_context_requirement_set_canonicalize(
    elpis_semantic_context_requirement_set_v1 *set);

/* ──────────────────────────────────────────────────────────────────── */
/* Persistence                                                         */
/* ──────────────────────────────────────────────────────────────────── */

/* Write requirement set atomically. Returns SEMANTIC_OK or SEMANTIC_E_IO.
 * Pre-existing destination is never overwritten. */
int elpis_write_requirement_set(const char *path,
                                 const elpis_semantic_context_requirement_set_v1 *set);

/* Read and validate requirement set. Recalculates identity.
 * Returns SEMANTIC_OK or SEMANTIC_E_IO on corruption. */
int elpis_read_requirement_set(const char *path,
                                elpis_semantic_context_requirement_set_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
