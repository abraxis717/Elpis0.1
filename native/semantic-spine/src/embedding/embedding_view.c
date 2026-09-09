/* embedding_view.c — Embedding-aware composed view extension.
 *
 * Extends P0 read-only view layer without changing P0 object identities.
 */
#include "elpis_semantic/embedding_view.h"
#include "elpis/sha256.h"
#include <stdlib.h>
#include <string.h>

/* ──────────────────────────────────────────────────────────────────── */
/* Embedding-aware composed view                                         */
/* ──────────────────────────────────────────────────────────────────── */

/* struct embedding_composed_view is defined in embedding_view.h */

/* ──────────────────────────────────────────────────────────────────── */
/* Creation/destruction                                                  */
/* ──────────────────────────────────────────────────────────────────── */

embedding_composed_view *embedding_composed_view_create(
    const semantic_snapshot_view *base_view,
    const semantic_query_overlay *overlay,
    const hacf_digest *policy_digest,
    const elpis_semantic_embedding_collection_v1 *collections,
    uint32_t col_count) {
    if (col_count && !collections) return NULL;
    embedding_composed_view *view = calloc(1, sizeof(*view));
    if (!view) return NULL;
    view->base_view = base_view;
    view->overlay = overlay;
    if (policy_digest) {
        memcpy(&view->policy_digest, policy_digest, sizeof(hacf_digest));
    }
    view->collections = collections;
    view->col_count = col_count;

    /* Extract all references from collections */
    if (collections && col_count > 0) {
        /* For now, we store a pointer to the collections — references
         * are resolved at query time. In a full implementation, we'd build
         * an index. */
    }

    /* Compute composed view digest */
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, &view->policy_digest, sizeof(hacf_digest));
    elpis_sha256_update(&ctx, &col_count, 4);
    for (uint32_t i = 0; i < col_count; i++) {
        elpis_sha256_update(&ctx, collections[i].collection_identity.bytes, 32);
    }
    elpis_sha256_final(&ctx, view->composed_view_digest.bytes);

    return view;
}

void embedding_composed_view_destroy(embedding_composed_view *view) {
    free(view);
}

int embedding_composed_view_digest(const embedding_composed_view *view, hacf_digest *out) {
    if (!view || !out) return -1;
    memcpy(out, &view->composed_view_digest, sizeof(hacf_digest));
    return 0;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Reference resolution (stub — full index-based resolution in production)
 *
 * In the P1 implementation, references are resolved from the collections.
 * The collections contain reference digests; the actual reference records
 * are stored separately and looked up by digest.
 *
 * For P1 qualification, we use a flat array approach where references are
 * passed alongside the view. */
/* ──────────────────────────────────────────────────────────────────── */

/* Helper: set references on the view (called from tests/integration).
 * This is a P1-specific extension — the view stores references directly
 * for resolution. */
void embedding_composed_view_set_refs(embedding_composed_view *view,
                                       const elpis_semantic_embedding_ref_v1 *refs,
                                       uint32_t ref_count) {
    if (!view || (ref_count && !refs)) return;
    view->refs = refs;
    view->ref_count = ref_count;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Reference queries                                                     */
/* ──────────────────────────────────────────────────────────────────── */

uint32_t embedding_composed_view_node_refs(
    const embedding_composed_view *view,
    const hacf_digest *node_digest,
    const elpis_semantic_embedding_ref_v1 **out_refs,
    uint32_t out_capacity) {
    if (!view || !node_digest || !view->refs || !out_refs || !out_capacity) return 0;

    /* Collect matching references */
    uint32_t count = 0;
    for (uint32_t i = 0; i < view->ref_count && count < out_capacity; i++) {
        if (memcmp(&view->refs[i].semantic_node_digest, node_digest, sizeof(hacf_digest)) == 0) {
            if (out_refs) out_refs[count] = &view->refs[i];
            count++;
        }
    }
    return count;
}

uint32_t embedding_composed_view_node_refs_by_profile(
    const embedding_composed_view *view,
    const hacf_digest *node_digest,
    const hacf_digest *profile_digest,
    const elpis_semantic_embedding_ref_v1 **out_refs,
    uint32_t out_capacity) {
    if (!view || !node_digest || !profile_digest || !view->refs || !out_refs || !out_capacity) return 0;

    uint32_t count = 0;
    for (uint32_t i = 0; i < view->ref_count && count < out_capacity; i++) {
        if (memcmp(&view->refs[i].semantic_node_digest, node_digest, sizeof(hacf_digest)) == 0 &&
            memcmp(&view->refs[i].embedding_profile_digest, profile_digest, sizeof(hacf_digest)) == 0) {
            if (out_refs) out_refs[count] = &view->refs[i];
            count++;
        }
    }
    return count;
}

uint32_t embedding_composed_view_node_refs_by_authority(
    const embedding_composed_view *view,
    const hacf_digest *node_digest,
    uint32_t min_authority,
    const elpis_semantic_embedding_ref_v1 **out_refs,
    uint32_t out_capacity) {
    if (!view || !node_digest || !view->refs || !out_refs || !out_capacity) return 0;

    uint32_t count = 0;
    for (uint32_t i = 0; i < view->ref_count && count < out_capacity; i++) {
        if (memcmp(&view->refs[i].semantic_node_digest, node_digest, sizeof(hacf_digest)) == 0 &&
            view->refs[i].authority >= min_authority) {
            if (out_refs) out_refs[count] = &view->refs[i];
            count++;
        }
    }
    return count;
}

uint32_t embedding_composed_view_node_refs_by_provenance(
    const embedding_composed_view *view,
    const hacf_digest *node_digest,
    const hacf_digest *provenance_digest,
    const elpis_semantic_embedding_ref_v1 **out_refs,
    uint32_t out_capacity) {
    if (!view || !node_digest || !provenance_digest || !view->refs || !out_refs || !out_capacity) return 0;

    uint32_t count = 0;
    for (uint32_t i = 0; i < view->ref_count && count < out_capacity; i++) {
        if (memcmp(&view->refs[i].semantic_node_digest, node_digest, sizeof(hacf_digest)) == 0 &&
            memcmp(&view->refs[i].provenance_digest, provenance_digest, sizeof(hacf_digest)) == 0) {
            if (out_refs) out_refs[count] = &view->refs[i];
            count++;
        }
    }
    return count;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Nodes for vector                                                        */
/* ──────────────────────────────────────────────────────────────────── */

uint32_t embedding_composed_view_nodes_for_vector(
    const embedding_composed_view *view,
    const hacf_digest *vector_digest,
    hacf_digest *out_nodes,
    uint32_t out_capacity) {
    if (!view || !vector_digest || !view->refs || !out_nodes || !out_capacity) return 0;

    uint32_t count = 0;
    for (uint32_t i = 0; i < view->ref_count && count < out_capacity; i++) {
        if (memcmp(&view->refs[i].embedding_vector_digest, vector_digest, sizeof(hacf_digest)) == 0) {
            /* Check for duplicate nodes */
            int dup = 0;
            for (uint32_t j = 0; j < count; j++) {
                if (memcmp(&out_nodes[j], &view->refs[i].semantic_node_digest, sizeof(hacf_digest)) == 0) {
                    dup = 1;
                    break;
                }
            }
            if (!dup) {
                if (out_nodes) memcpy(&out_nodes[count], &view->refs[i].semantic_node_digest, sizeof(hacf_digest));
                count++;
            }
        }
    }
    return count;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Enumeration                                                           */
/* ──────────────────────────────────────────────────────────────────── */

static int node_pointer_cmp(const void *pa, const void *pb) {
    const elpis_semantic_node_v1 *a = *(const elpis_semantic_node_v1 *const *)pa;
    const elpis_semantic_node_v1 *b = *(const elpis_semantic_node_v1 *const *)pb;
    return elpis_semantic_node_cmp(a, b);
}

uint32_t embedding_composed_view_enumerate_embedded_nodes(
    const embedding_composed_view *view,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_node_v1 **out_nodes,
    uint32_t out_capacity) {
    if (!view || !view->base_view || !view->refs || !view->ref_count ||
        !out_nodes || !out_capacity || !limit) return 0;
    if (view->ref_count != 0 && SIZE_MAX / (size_t)view->ref_count < sizeof(*out_nodes)) return 0;
    const elpis_semantic_node_v1 **nodes = malloc((size_t)view->ref_count * sizeof(*nodes));
    if (!nodes) return 0;
    uint32_t found = 0;
    for (uint32_t i = 0; i < view->ref_count; ++i) {
        const elpis_semantic_node_v1 *node = semantic_view_lookup_node(
            view->base_view, &view->refs[i].semantic_node_digest);
        if (node) nodes[found++] = node;
    }
    qsort(nodes, found, sizeof(*nodes), node_pointer_cmp);
    uint32_t placed = 0;
    for (uint32_t i = 0; i < found; ++i) {
        if (i && elpis_semantic_node_cmp(nodes[i - 1], nodes[i]) == 0) continue;
        if (offset) { --offset; continue; }
        out_nodes[placed++] = nodes[i];
        if (placed == limit || placed == out_capacity) break;
    }
    free(nodes);
    return placed;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Collection queries                                                    */
/* ──────────────────────────────────────────────────────────────────── */

uint32_t embedding_composed_view_base_collection_count(const embedding_composed_view *view) {
    if (!view) return 0;
    uint32_t count = 0;
    for (uint32_t i = 0; i < view->col_count; i++) {
        if (view->collections[i].target_kind == EMBEDDING_TARGET_BASE_SNAPSHOT) count++;
    }
    return count;
}

uint32_t embedding_composed_view_overlay_collection_count(const embedding_composed_view *view) {
    if (!view) return 0;
    uint32_t count = 0;
    for (uint32_t i = 0; i < view->col_count; i++) {
        if (view->collections[i].target_kind == EMBEDDING_TARGET_QUERY_OVERLAY) count++;
    }
    return count;
}

uint32_t embedding_composed_view_collections(
    const embedding_composed_view *view,
    uint32_t offset, uint32_t limit,
    const elpis_semantic_embedding_collection_v1 **out,
    uint32_t out_capacity) {
    if (!view || !view->collections || !out || !out_capacity || !limit) return 0;
    if (offset >= view->col_count) return 0;
    uint32_t remaining = view->col_count - offset;
    uint32_t take = (remaining < limit) ? remaining : limit;
    take = (take < out_capacity) ? take : out_capacity;
    for (uint32_t i = 0; i < take; i++) {
        out[i] = &view->collections[offset + i];
    }
    return take;
}
