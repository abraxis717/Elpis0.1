/* query_overlay.c — Immutable per-query overlays with composed views.
 *
 * Overlay can add query-local nodes, hyperedges, assertions, incidences.
 * May reference base snapshot nodes but cannot alter/delete them.
 * Composed view = base + overlay with deterministic identity.
 */
#include "elpis_semantic/query_overlay.h"
#include "elpis/sha256.h"
#include "builder_internal.h"
#include "view_internal.h"
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>

/* ──────────────────────────────────────────────────────────────────── */
/* Overlay                                                             */
/* ──────────────────────────────────────────────────────────────────── */

semantic_query_overlay *semantic_overlay_create(
    const semantic_snapshot_manifest *base_manifest,
    const semantic_type_registry *registry,
    const hacf_digest *query_digest) {
    if (!base_manifest || !registry || !query_digest) return NULL;

    semantic_query_overlay *overlay = calloc(1, sizeof(*overlay));
    if (!overlay) return NULL;

    overlay->abi_version = SEMANTIC_OVERLAY_ABI_VERSION;
    semantic_snapshot_digest(base_manifest, &overlay->base_snapshot_manifest_digest);
    overlay->query_digest = *query_digest;
    /* base_hacf_graph_snapshot_digest from manifest. */
    overlay->base_hacf_graph_snapshot_digest = base_manifest->hacf_graph_snapshot_digest;

    /* Create local builder for query-local records. */
    overlay->local_builder = semantic_builder_create(registry);
    if (!overlay->local_builder) { free(overlay); return NULL; }

    return overlay;
}

void semantic_overlay_destroy(semantic_query_overlay *overlay) {
    if (!overlay) return;
    if (overlay->local_builder) {
        semantic_builder_destroy(overlay->local_builder);
    }
    free(overlay);
}

int semantic_overlay_add_node(semantic_query_overlay *overlay,
                               const elpis_semantic_node_v1 *node) {
    if (!overlay || !node) return SEMANTIC_E_INVAL;
    return semantic_builder_add_node(overlay->local_builder, node);
}

int semantic_overlay_add_hyperedge(semantic_query_overlay *overlay,
                                    const elpis_semantic_hyperedge_v1 *edge) {
    if (!overlay || !edge) return SEMANTIC_E_INVAL;
    return semantic_builder_add_hyperedge(overlay->local_builder, edge);
}

int semantic_overlay_add_assertion(semantic_query_overlay *overlay,
                                    const elpis_semantic_assertion_v1 *assertion) {
    if (!overlay || !assertion) return SEMANTIC_E_INVAL;
    return semantic_builder_add_assertion(overlay->local_builder, assertion);
}

int semantic_overlay_add_incidence(semantic_query_overlay *overlay,
                                    const elpis_semantic_incidence_v1 *incidence) {
    if (!overlay || !incidence) return SEMANTIC_E_INVAL;
    return semantic_builder_add_incidence(overlay->local_builder, incidence);
}

int semantic_overlay_add_external_dependency(semantic_query_overlay *overlay,
                                              const hacf_digest *dep_digest) {
    if (!overlay || !dep_digest) return SEMANTIC_E_INVAL;
    if (overlay->external_dependency_count >= SEMANTIC_MAX_EXTERNAL_DEPS) return SEMANTIC_E_NOMEM;
    overlay->external_dependency_digests[overlay->external_dependency_count++] = *dep_digest;
    return SEMANTIC_OK;
}

int semantic_overlay_finalize(semantic_query_overlay *overlay) {
    if (!overlay) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    const char *domain = "elpis.semantic.overlay.v1";
    uint32_t be_len = htonl((uint32_t)strlen(domain));
    elpis_sha256_update(&ctx, &be_len, 4);
    elpis_sha256_update(&ctx, domain, strlen(domain));

    uint32_t be = htonl(overlay->abi_version);
    elpis_sha256_update(&ctx, &be, 4);
    elpis_sha256_update(&ctx, overlay->base_snapshot_manifest_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, overlay->base_hacf_graph_snapshot_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, overlay->query_digest.bytes, HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx, overlay->overlay_policy_digest.bytes, HACF_DIGEST_BYTES);
    be = htonl(overlay->external_dependency_count);
    elpis_sha256_update(&ctx, &be, 4);
    for (uint32_t i = 0; i < overlay->external_dependency_count; i++) {
        elpis_sha256_update(&ctx, overlay->external_dependency_digests[i].bytes, HACF_DIGEST_BYTES);
    }

    /* Query-local segment digest from the builder. */
    if (overlay->local_builder) {
        be = htonl(semantic_builder_node_count(overlay->local_builder));
        elpis_sha256_update(&ctx, &be, 4);
        be = htonl(semantic_builder_assertion_count(overlay->local_builder));
        elpis_sha256_update(&ctx, &be, 4);
        be = htonl(semantic_builder_hyperedge_count(overlay->local_builder));
        elpis_sha256_update(&ctx, &be, 4);
        be = htonl(semantic_builder_incidence_count(overlay->local_builder));
        elpis_sha256_update(&ctx, &be, 4);
    }

    elpis_sha256_final(&ctx, overlay->overlay_identity.bytes);
    return SEMANTIC_OK;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Composed view                                                       */
/* ──────────────────────────────────────────────────────────────────── */

struct semantic_composed_view {
    const semantic_snapshot_view *base_view;
    const semantic_query_overlay *overlay;
    hacf_digest policy_digest;
    hacf_digest composed_view_digest;
    int finalized;
};

semantic_composed_view *semantic_composed_view_create(
    const semantic_snapshot_view *base_view,
    const semantic_query_overlay *overlay,
    const hacf_digest *policy_digest) {
    if (!base_view || !overlay || !policy_digest) return NULL;

    semantic_composed_view *cv = calloc(1, sizeof(*cv));
    if (!cv) return NULL;

    cv->base_view = base_view;
    cv->overlay = overlay;
    cv->policy_digest = *policy_digest;
    cv->finalized = 0;

    /* Compute composed view digest. */
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);

    const char *domain = "elpis.semantic.composed_view.v1";
    uint32_t be_len = htonl((uint32_t)strlen(domain));
    elpis_sha256_update(&ctx, &be_len, 4);
    elpis_sha256_update(&ctx, domain, strlen(domain));

    /* Base identity from manifest digest. */
    elpis_sha256_update(&ctx, overlay->base_snapshot_manifest_digest.bytes, HACF_DIGEST_BYTES);
    /* Overlay identity. */
    elpis_sha256_update(&ctx, overlay->overlay_identity.bytes, HACF_DIGEST_BYTES);
    /* Policy digest. */
    elpis_sha256_update(&ctx, cv->policy_digest.bytes, HACF_DIGEST_BYTES);

    elpis_sha256_final(&ctx, cv->composed_view_digest.bytes);
    cv->finalized = 1;

    return cv;
}

void semantic_composed_view_destroy(semantic_composed_view *view) {
    free(view);
}

int semantic_composed_view_digest(const semantic_composed_view *view, hacf_digest *out) {
    if (!view || !out || !view->finalized) return SEMANTIC_E_INVAL;
    *out = view->composed_view_digest;
    return SEMANTIC_OK;
}

const elpis_semantic_node_v1 *semantic_composed_view_lookup_node(
    const semantic_composed_view *view, const hacf_digest *node_identity) {
    if (!view || !node_identity) return NULL;
    /* Overlay shadows base — check overlay first. */
    if (view->overlay && view->overlay->local_builder) {
        for (uint32_t i = 0; i < semantic_builder_node_count(view->overlay->local_builder); i++) {
            const elpis_semantic_node_v1 *n = semantic_builder_get_node(view->overlay->local_builder, i);
            if (n && memcmp(&n->node_identity, node_identity, HACF_DIGEST_BYTES) == 0)
                return n;
        }
    }
    /* Then base. */
    return semantic_view_lookup_node(view->base_view, node_identity);
}

const elpis_semantic_hyperedge_v1 *semantic_composed_view_lookup_hyperedge(
    const semantic_composed_view *view, const hacf_digest *hyperedge_identity) {
    if (!view || !hyperedge_identity) return NULL;
    if (view->overlay && view->overlay->local_builder) {
        for (uint32_t i = 0; i < semantic_builder_hyperedge_count(view->overlay->local_builder); i++) {
            const elpis_semantic_hyperedge_v1 *e = semantic_builder_get_hyperedge(view->overlay->local_builder, i);
            if (e && memcmp(&e->hyperedge_identity, hyperedge_identity, HACF_DIGEST_BYTES) == 0)
                return e;
        }
    }
    return semantic_view_lookup_hyperedge(view->base_view, hyperedge_identity);
}

uint32_t semantic_composed_view_enumerate_nodes(
    const semantic_composed_view *view,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_node_v1 **out, uint32_t out_capacity) {
    if (!view || !out) return 0;
    *out = NULL;

    uint32_t count = 0;
    /* Base nodes first (already canonical), then overlay nodes not in base. */
    const semantic_snapshot_view *base = view->base_view;
    for (uint32_t i = 0; i < base->node_count; i++) {
        if (count < out_capacity) out[count] = &base->nodes[i];
        count++;
    }
    if (view->overlay && view->overlay->local_builder) {
        for (uint32_t i = 0; i < semantic_builder_node_count(view->overlay->local_builder); i++) {
            const elpis_semantic_node_v1 *n = semantic_builder_get_node(view->overlay->local_builder, i);
            if (!n) continue;
            /* Skip if already in base (overlay shadows, don't duplicate). */
            if (semantic_view_lookup_node(base, &n->node_identity)) continue;
            if (count < out_capacity) out[count] = n;
            count++;
        }
    }
    return count;
}

uint32_t semantic_composed_view_total_nodes(const semantic_composed_view *view) {
    if (!view) return 0;
    uint32_t total = semantic_view_total_nodes(view->base_view);
    if (view->overlay && view->overlay->local_builder) {
        total += semantic_builder_node_count(view->overlay->local_builder);
    }
    return total;
}

uint32_t semantic_composed_view_total_hyperedges(const semantic_composed_view *view) {
    if (!view) return 0;
    uint32_t total = semantic_view_total_hyperedges(view->base_view);
    if (view->overlay && view->overlay->local_builder) {
        total += semantic_builder_hyperedge_count(view->overlay->local_builder);
    }
    return total;
}

int semantic_composed_view_base_identity(const semantic_composed_view *view, hacf_digest *out) {
    if (!view || !out) return SEMANTIC_E_INVAL;
    *out = view->overlay->base_snapshot_manifest_digest;
    return SEMANTIC_OK;
}

int semantic_composed_view_overlay_identity(const semantic_composed_view *view, hacf_digest *out) {
    if (!view || !out) return SEMANTIC_E_INVAL;
    *out = view->overlay->overlay_identity;
    return SEMANTIC_OK;
}
