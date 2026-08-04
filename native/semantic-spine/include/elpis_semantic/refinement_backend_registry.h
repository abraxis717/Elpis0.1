/* elpis_semantic/refinement_backend_registry.h — Backend registry v1.
 *
 * Maintains the set of registered refinement backends. Exactly one backend
 * may be ACTIVE_CANONICAL. Registry fails closed on any identity mismatch.
 *
 * Identity domain: "elpis.semantic.refinement_backend_registry.v1"
 */
#ifndef ELPIS_SEMANTIC_REFINEMENT_BACKEND_REGISTRY_H
#define ELPIS_SEMANTIC_REFINEMENT_BACKEND_REGISTRY_H

#include "elpis_semantic/refinement_backend.h"
#include "elpis/cascade.h"
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define REFINEMENT_BACKEND_REGISTRY_VERSION 1u
#define REFINEMENT_MAX_BACKENDS 8u

/* ──────────────────────────────────────────────────────────────────── */
/* Registry state                                                         */
/* ──────────────────────────────────────────────────────────────────── */

typedef struct elpis_semantic_refinement_backend_registry_v1 {
    uint32_t                              abi_version;

    /* Registered backends */
    uint32_t                              backend_count;
    elpis_semantic_refinement_backend_v1  backends[REFINEMENT_MAX_BACKENDS];

    /* Active canonical identity (digest of the one active canonical backend) */
    hacf_digest                           active_canonical_digest;

    /* P11 selection binding */
    hacf_digest                           P11_final_report_digest;
    hacf_digest                           P11_selection_result_digest;
    hacf_digest                           P11_replacement_handoff_digest;

    /* Registry identity */
    hacf_digest                           registry_digest;

    uint8_t                               reserved[64];
} elpis_semantic_refinement_backend_registry_v1;

/* Initialize: set ABI version, zero everything else. */
void elpis_refinement_backend_registry_init(
    elpis_semantic_refinement_backend_registry_v1 *registry);

/* Add a backend to the registry. Fails closed if:
 * - registry is full
 * - name already exists
 * - would cause >1 active canonical
 * - backend itself fails validation */
int elpis_refinement_backend_registry_add(
    elpis_semantic_refinement_backend_registry_v1 *registry,
    const elpis_semantic_refinement_backend_v1 *backend);

/* Resolve the active canonical backend. Returns pointer or NULL if none. */
const elpis_semantic_refinement_backend_v1 *
elpis_refinement_backend_registry_resolve_canonical(
    const elpis_semantic_refinement_backend_registry_v1 *registry);

/* Resolve a backend by name. Returns pointer or NULL. */
const elpis_semantic_refinement_backend_v1 *
elpis_refinement_backend_registry_resolve_by_name(
    const elpis_semantic_refinement_backend_registry_v1 *registry,
    const char *name);

/* Validate registry: exactly one active canonical, identity matches P11. */
int elpis_refinement_backend_registry_validate(
    const elpis_semantic_refinement_backend_registry_v1 *registry);

/* Compute registry identity. Domain: "elpis.semantic.refinement_backend_registry.v1" */
int elpis_refinement_backend_registry_identity(
    const elpis_semantic_refinement_backend_registry_v1 *registry, hacf_digest *out);

/* Persistence */
int elpis_write_refinement_backend_registry(const char *path,
    const elpis_semantic_refinement_backend_registry_v1 *registry);
int elpis_read_refinement_backend_registry(const char *path,
    elpis_semantic_refinement_backend_registry_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
