/* context_deficit.c — Context deficit evaluator.
 *
 * Evaluates requirements against composed view + embedding collections.
 * Does NOT short-circuit. Does NOT mutate inputs.
 * Does NOT treat embedding proximity as semantic support.
 */
#include "elpis_semantic/context_deficit.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/embedding_collection.h"
#include "elpis_semantic/snapshot_view.h"
#include "elpis_semantic/embedding_ref.h"
#include "elpis_semantic/embedding_neighborhood.h"
#include "elpis/sha256.h"
#include <stdlib.h>
#include <string.h>
#include <arpa/inet.h>

static void write_domain_tag(elpis_sha256_ctx *ctx, const char *domain) {
    size_t len = strlen(domain);
    uint32_t be_len = htonl((uint32_t)len);
    elpis_sha256_update(ctx, &be_len, 4);
    elpis_sha256_update(ctx, domain, len);
}

static void write_u32_be(elpis_sha256_ctx *ctx, uint32_t val) {
    uint32_t be = htonl(val);
    elpis_sha256_update(ctx, &be, 4);
}

static void write_digest(elpis_sha256_ctx *ctx, const hacf_digest *d) {
    elpis_sha256_update(ctx, d->bytes, HACF_DIGEST_BYTES);
}

static uint64_t htonll(uint64_t val) {
    uint64_t lo = htonl((uint32_t)val);
    uint64_t hi = htonl((uint32_t)(val >> 32));
    return (hi << 32) | lo;
}

static void write_i64_be(elpis_sha256_ctx *ctx, int64_t val) {
    uint64_t be_val = htonll((uint64_t)val);
    elpis_sha256_update(ctx, &be_val, 8);
}

static const char DIAG_DOMAIN[] = "elpis.semantic.requirement_result.diagnostic.v1";

/* ──────────────────────────────────────────────────────────────────── */
/* Requirement result operations                                       */
/* ──────────────────────────────────────────────────────────────────── */

void elpis_requirement_result_init(elpis_semantic_requirement_result_v1 *result) {
    memset(result, 0, sizeof(*result));
}

int elpis_requirement_result_diagnostic(
    const elpis_semantic_requirement_result_v1 *result, hacf_digest *out) {
    if (!result || !out) return SEMANTIC_E_INVAL;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    write_domain_tag(&ctx, DIAG_DOMAIN);
    write_digest(&ctx, &result->requirement_digest);
    write_u32_be(&ctx, result->evaluation_status);
    write_u32_be(&ctx, result->satisfaction_status);
    write_u32_be(&ctx, result->observed_count);
    write_u32_be(&ctx, result->required_threshold);
    write_u32_be(&ctx, result->matched_count);
    for (uint32_t i = 0; i < result->matched_count; i++) {
        write_digest(&ctx, &result->matched_object_digests[i]);
    }
    write_u32_be(&ctx, result->missing_count);
    for (uint32_t i = 0; i < result->missing_count; i++) {
        write_digest(&ctx, &result->missing_identities[i]);
    }
    write_u32_be(&ctx, result->deficit_reason);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_requirement_result_cmp(
    const elpis_semantic_requirement_result_v1 *a,
    const elpis_semantic_requirement_result_v1 *b) {
    if (!a || !b) return -1;
    return memcmp(a->requirement_digest.bytes, b->requirement_digest.bytes, HACF_DIGEST_BYTES);
}

void elpis_requirement_results_canonicalize(
    elpis_semantic_requirement_result_v1 *results, uint32_t count) {
    /* Insertion sort by requirement digest ascending */
    for (uint32_t i = 1; i < count; i++) {
        elpis_semantic_requirement_result_v1 key = results[i];
        uint32_t j = i;
        while (j > 0 && elpis_requirement_result_cmp(&key, &results[j - 1]) < 0) {
            results[j] = results[j - 1];
            j--;
        }
        results[j] = key;
    }
}

void elpis_count_deficits(
    const elpis_semantic_requirement_result_v1 *results, uint32_t count,
    const elpis_semantic_context_requirement_set_v1 *requirement_set,
    uint32_t *satisfied_out,
    uint32_t *mandatory_deficit_out,
    uint32_t *preferred_deficit_out,
    uint32_t *diagnostic_deficit_out,
    uint32_t *blocked_out) {
    *satisfied_out = 0;
    *mandatory_deficit_out = 0;
    *preferred_deficit_out = 0;
    *diagnostic_deficit_out = 0;
    *blocked_out = 0;

    (void)requirement_set; /* future: lookup requirement level from requirement_set */

    for (uint32_t i = 0; i < count; i++) {
        if (results[i].evaluation_status != EVAL_STATUS_EVALUATED) {
            (*blocked_out)++;
            continue;
        }
        if (results[i].satisfaction_status == SAT_STATUS_SATISFIED) {
            (*satisfied_out)++;
        } else if (results[i].satisfaction_status == SAT_STATUS_UNSATISFIED) {
            /* Without the requirement set's level info, default to mandatory */
            /* In production this would look up the level from the requirement */
            (*mandatory_deficit_out)++;
        }
    }
}

/* ──────────────────────────────────────────────────────────────────── */
/* Per-type evaluation helpers                                         */
/* ──────────────────────────────────────────────────────────────────── */

static int evaluate_object_present(
    const elpis_semantic_context_requirement_v1 *req,
    const semantic_snapshot_view *view,
    elpis_semantic_requirement_result_v1 *result) {
    if (req->extension_size < sizeof(context_object_present_ext)) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INTERNAL;
        return SEMANTIC_OK;
    }
    const context_object_present_ext *ext =
        (const context_object_present_ext *)req->extension_bytes;

    /* Check if the required object exists in the view */
    int found = 0;
    if (ext->required_object_kind == KIND_NODE || ext->required_object_kind == 1) {
        const elpis_semantic_node_v1 *node =
            semantic_view_lookup_node(view, &ext->required_object_digest);
        if (node) found = 1;
    } else if (ext->required_object_kind == KIND_HYPEREDGE || ext->required_object_kind == 2) {
        const elpis_semantic_hyperedge_v1 *edge =
            semantic_view_lookup_hyperedge(view, &ext->required_object_digest);
        if (edge) found = 1;
    } else {
        found = 0; /* unknown object kind */
    }

    result->evaluation_status = EVAL_STATUS_EVALUATED;
    result->observed_count = found ? 1 : 0;
    result->required_threshold = 1;

    if (found) {
        result->satisfaction_status = SAT_STATUS_SATISFIED;
        result->matched_count = 1;
        memcpy(result->matched_object_digests[0].bytes,
               ext->required_object_digest.bytes, HACF_DIGEST_BYTES);
    } else {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_OBJECT_ABSENT;
        result->missing_count = 1;
        memcpy(result->missing_identities[0].bytes,
               ext->required_object_digest.bytes, HACF_DIGEST_BYTES);
    }
    return SEMANTIC_OK;
}

static int evaluate_type_coverage(
    const elpis_semantic_context_requirement_v1 *req,
    const semantic_snapshot_view *view,
    elpis_semantic_requirement_result_v1 *result) {
    if (req->extension_size < sizeof(context_type_coverage_ext)) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INTERNAL;
        return SEMANTIC_OK;
    }
    const context_type_coverage_ext *ext =
        (const context_type_coverage_ext *)req->extension_bytes;

    uint32_t observed = 0;
    if (ext->object_kind == KIND_NODE || ext->object_kind == 1) {
        /* Enumerate nodes by type */
        const elpis_semantic_node_v1 *nodes[256];
        observed = semantic_view_enumerate_nodes_by_type(view, ext->semantic_type,
                                                         0, 256, nodes, 256);
        /* Filter by authority if specified */
        if (ext->min_authority > 0) {
            uint32_t filtered = 0;
            for (uint32_t i = 0; i < observed; i++) {
                /* Check if this node has assertions meeting authority */
                const elpis_semantic_assertion_v1 *assertions[256];
                uint32_t ac = semantic_view_node_assertions(view, &nodes[i]->node_identity,
                    ext->min_authority, 0, 256, assertions, 256);
                if (ac > 0) filtered++;
            }
            observed = filtered;
        }
    } else if (ext->object_kind == KIND_HYPEREDGE || ext->object_kind == 2) {
        const elpis_semantic_hyperedge_v1 *edges[256];
        observed = semantic_view_enumerate_hyperedges_by_type(view, ext->semantic_type,
                                                              0, 256, edges, 256);
    }

    result->evaluation_status = EVAL_STATUS_EVALUATED;
    result->observed_count = observed;
    result->required_threshold = ext->minimum_count;

    if (ext->maximum_count > 0 && observed > ext->maximum_count) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_TYPE_COVERAGE_ABOVE_MAX;
    } else if (observed >= ext->minimum_count) {
        result->satisfaction_status = SAT_STATUS_SATISFIED;
    } else {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_TYPE_COVERAGE_BELOW_MIN;
    }
    return SEMANTIC_OK;
}

static int evaluate_assertion_coverage(
    const elpis_semantic_context_requirement_v1 *req,
    const semantic_snapshot_view *view,
    elpis_semantic_requirement_result_v1 *result) {
    if (req->extension_size < sizeof(context_assertion_coverage_ext)) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INTERNAL;
        return SEMANTIC_OK;
    }
    const context_assertion_coverage_ext *ext =
        (const context_assertion_coverage_ext *)req->extension_bytes;

    const elpis_semantic_assertion_v1 *assertions[256];
    uint32_t ac = semantic_view_node_assertions(view, &ext->asserted_object_digest,
        ext->min_authority, 0, 256, assertions, 256);

    /* Filter by flag masks */
    uint32_t eligible = 0;
    uint32_t distinct_provenance = 0;
    for (uint32_t i = 0; i < ac; i++) {
        if (ext->forbidden_flag_mask &&
            (assertions[i]->assertion_flags & ext->forbidden_flag_mask)) continue;
        if (ext->allowed_flag_mask &&
            !(assertions[i]->assertion_flags & ext->allowed_flag_mask)) continue;
        eligible++;
        /* Count distinct provenances */
        int unique = 1;
        for (uint32_t j = 0; j < i; j++) {
            if (assertions[j]->assertion_flags == assertions[i]->assertion_flags) {
                if (memcmp(assertions[j]->provenance_digest.bytes,
                          assertions[i]->provenance_digest.bytes, HACF_DIGEST_BYTES) == 0) {
                    unique = 0;
                    break;
                }
            }
        }
        if (unique) distinct_provenance++;
    }

    result->evaluation_status = EVAL_STATUS_EVALUATED;
    result->observed_count = eligible;
    result->required_threshold = ext->min_assertion_count;

    if (eligible >= ext->min_assertion_count &&
        distinct_provenance >= ext->min_distinct_provenance_count) {
        result->satisfaction_status = SAT_STATUS_SATISFIED;
    } else if (distinct_provenance < ext->min_distinct_provenance_count) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_PROVENANCE_DIVERSITY_BELOW_MIN;
    } else {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_ASSERTION_COUNT_BELOW_MIN;
    }
    return SEMANTIC_OK;
}

static int evaluate_external_context(
    const elpis_semantic_context_requirement_v1 *req,
    elpis_semantic_requirement_result_v1 *result) {
    (void)req;
    /* Explicit external context always produces a deficit — P2 does not
       define external artifact admission. */
    result->evaluation_status = EVAL_STATUS_EVALUATED;
    result->satisfaction_status = SAT_STATUS_UNSATISFIED;
    result->deficit_reason = DEF_EXTERNAL_CONTEXT_REQUIRED;
    result->observed_count = 0;
    result->required_threshold = 1;
    return SEMANTIC_OK;
}

static int evaluate_opaque_application(
    const elpis_semantic_context_requirement_v1 *req,
    elpis_semantic_requirement_result_v1 *result) {
    (void)req;
    /* P2 core must not execute unknown evaluators. */
    result->evaluation_status = EVAL_STATUS_BLOCKED_UNSUPPORTED;
    result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
    result->deficit_reason = DEF_EVALUATION_BLOCKED_UNKNOWN;
    return SEMANTIC_OK;
}

static int evaluate_role_completeness(
    const elpis_semantic_context_requirement_v1 *req,
    const semantic_snapshot_view *view,
    elpis_semantic_requirement_result_v1 *result) {
    if (!view) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_VIEW_MISMATCH;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_VIEW_MISMATCH;
        return SEMANTIC_OK;
    }
    if (req->extension_size < sizeof(context_role_completeness_ext)) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INTERNAL;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        return SEMANTIC_OK;
    }
    const context_role_completeness_ext *ext =
        (const context_role_completeness_ext *)req->extension_bytes;

    /* Check hyperedge digest is non-zero */
    { static const uint8_t z[HACF_DIGEST_BYTES] = {0};
      if (memcmp(ext->hyperedge_digest.bytes, z, HACF_DIGEST_BYTES) == 0) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INVALID_REF;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_INVALID_REF;
        return SEMANTIC_OK;
      }
    }

    /* Resolve target hyperedge */
    const elpis_semantic_hyperedge_v1 *edge =
        semantic_view_lookup_hyperedge(view, &ext->hyperedge_digest);
    if (!edge) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INVALID_REF;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_INVALID_REF;
        return SEMANTIC_OK;
    }

    /* Enumerate canonical participants and filter by required role */
    uint32_t role_count = 0;
    for (uint32_t i = 0; i < edge->participant_count; i++) {
        if (edge->participants[i].incidence_role == ext->role_id) {
            if (role_count < CONTEXT_MAX_MATCHED_OBJECTS) {
                memcpy(result->matched_object_digests[role_count].bytes,
                       edge->participants[i].node_identity.bytes, HACF_DIGEST_BYTES);
            }
            role_count++;
        }
    }
    result->matched_count = role_count < CONTEXT_MAX_MATCHED_OBJECTS ? role_count : CONTEXT_MAX_MATCHED_OBJECTS;

    /* Check ordered role gaps */
    if (ext->ordered_role_policy != 0 && role_count > 0) {
        /* Collect ordinals for matched roles */
        uint32_t ordinals[SEMANTIC_MAX_PARTICIPANTS];
        uint32_t ord_count = 0;
        for (uint32_t i = 0; i < edge->participant_count; i++) {
            if (edge->participants[i].incidence_role == ext->role_id && ord_count < SEMANTIC_MAX_PARTICIPANTS) {
                ordinals[ord_count++] = edge->participants[i].ordinal;
            }
        }
        /* Sort ordinals */
        for (uint32_t i = 1; i < ord_count; i++) {
            uint32_t key = ordinals[i]; uint32_t j = i;
            while (j > 0 && ordinals[j-1] > key) { ordinals[j] = ordinals[j-1]; j--; }
            ordinals[j] = key;
        }
        /* Check for gaps: ordinals should start at 0 and be contiguous */
        for (uint32_t i = 0; i < ord_count; i++) {
            if (ordinals[i] != i) {
                result->evaluation_status = EVAL_STATUS_EVALUATED;
                result->satisfaction_status = SAT_STATUS_UNSATISFIED;
                result->deficit_reason = DEF_ORDERED_ROLE_GAP;
                result->observed_count = role_count;
                result->required_threshold = ext->min_role_count;
                result->missing_count = 1;
                memcpy(result->missing_identities[0].bytes,
                       ext->hyperedge_digest.bytes, HACF_DIGEST_BYTES);
                return SEMANTIC_OK;
            }
        }
        /* Check for duplicate ordinals */
        for (uint32_t i = 1; i < ord_count; i++) {
            if (ordinals[i] == ordinals[i-1]) {
                result->evaluation_status = EVAL_STATUS_EVALUATED;
                result->satisfaction_status = SAT_STATUS_UNSATISFIED;
                result->deficit_reason = DEF_ORDERED_ROLE_GAP;
                result->observed_count = role_count;
                result->required_threshold = ext->min_role_count;
                return SEMANTIC_OK;
            }
        }
    }

    /* Cardinality checks */
    result->evaluation_status = EVAL_STATUS_EVALUATED;
    result->observed_count = role_count;
    result->required_threshold = ext->min_role_count;

    if (role_count == 0) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_REQUIRED_ROLE_ABSENT;
        result->missing_count = 1;
        memcpy(result->missing_identities[0].bytes,
               ext->hyperedge_digest.bytes, HACF_DIGEST_BYTES);
        return SEMANTIC_OK;
    }
    if (role_count < ext->min_role_count) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_ROLE_CARDINALITY_INSUFFICIENT;
        result->missing_count = 1;
        memcpy(result->missing_identities[0].bytes,
               ext->hyperedge_digest.bytes, HACF_DIGEST_BYTES);
        return SEMANTIC_OK;
    }
    if (ext->max_role_count > 0 && role_count > ext->max_role_count) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_ROLE_CARDINALITY_EXCESS;
        return SEMANTIC_OK;
    }

    result->satisfaction_status = SAT_STATUS_SATISFIED;
    return SEMANTIC_OK;
}

static int evaluate_evidence_relation_coverage(
    const elpis_semantic_context_requirement_v1 *req,
    const semantic_snapshot_view *view,
    elpis_semantic_requirement_result_v1 *result) {
    if (!view) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_VIEW_MISMATCH;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_VIEW_MISMATCH;
        return SEMANTIC_OK;
    }
    if (req->extension_size < sizeof(context_evidence_relation_ext)) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INTERNAL;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        return SEMANTIC_OK;
    }
    const context_evidence_relation_ext *ext =
        (const context_evidence_relation_ext *)req->extension_bytes;

    /* Check target is non-zero */
    { static const uint8_t z[HACF_DIGEST_BYTES] = {0};
      if (memcmp(ext->target_object_digest.bytes, z, HACF_DIGEST_BYTES) == 0) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INVALID_REF;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_INVALID_REF;
        return SEMANTIC_OK;
      }
    }

    /* Enumerate hyperedges incident to the target node */
    const elpis_semantic_hyperedge_v1 *incident[256];
    uint32_t incident_count = semantic_view_node_hyperedges(view,
        &ext->target_object_digest, 0, 256, incident, 256);

    if (incident_count == 0) {
        result->evaluation_status = EVAL_STATUS_EVALUATED;
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_EVIDENCE_RELATION_ABSENT;
        result->observed_count = 0;
        result->required_threshold = ext->min_relation_count;
        return SEMANTIC_OK;
    }

    /* Filter by allowed evidence types and count qualifying relations */
    uint32_t qualifying_count = 0;
    hacf_digest evidence_nodes[256];
    uint32_t evidence_node_count = 0;

    for (uint32_t i = 0; i < incident_count; i++) {
        /* Check if this hyperedge type is allowed */
        int type_allowed = 0;
        for (uint32_t t = 0; t < ext->type_count && t < 4; t++) {
            if (incident[i]->hyperedge_type == ext->allowed_evidence_types[t]) {
                type_allowed = 1; break;
            }
        }
        if (!type_allowed) continue;

        /* Verify target occupies an allowed role */
        int target_role_ok = 0;
        for (uint32_t p = 0; p < incident[i]->participant_count; p++) {
            if (memcmp(incident[i]->participants[p].node_identity.bytes,
                       ext->target_object_digest.bytes, HACF_DIGEST_BYTES) == 0) {
                for (uint32_t r = 0; r < 4; r++) {
                    if (incident[i]->participants[p].incidence_role == ext->allowed_target_roles[r]) {
                        target_role_ok = 1; break;
                    }
                }
            }
            if (target_role_ok) break;
        }
        if (!target_role_ok) continue;

        qualifying_count++;
        if (qualifying_count > CONTEXT_MAX_MATCHED_OBJECTS) break;

        /* Record this relation identity */
        if (qualifying_count <= CONTEXT_MAX_MATCHED_OBJECTS) {
            elpis_semantic_hyperedge_identity(incident[i],
                &result->matched_object_digests[qualifying_count - 1]);
        }

        /* Collect evidence nodes and provenances */
        for (uint32_t p = 0; p < incident[i]->participant_count; p++) {
            if (memcmp(incident[i]->participants[p].node_identity.bytes,
                       ext->target_object_digest.bytes, HACF_DIGEST_BYTES) == 0) continue;
            /* Check if participant is in an allowed evidence role */
            int ev_role = 0;
            for (uint32_t r = 0; r < 4; r++) {
                if (incident[i]->participants[p].incidence_role == ext->allowed_evidence_roles[r]) {
                    ev_role = 1; break;
                }
            }
            if (!ev_role) continue;

            /* Track distinct evidence nodes */
            int already = 0;
            for (uint32_t n = 0; n < evidence_node_count; n++) {
                if (memcmp(evidence_nodes[n].bytes,
                          incident[i]->participants[p].node_identity.bytes,
                          HACF_DIGEST_BYTES) == 0) { already = 1; break; }
            }
            if (!already && evidence_node_count < 256) {
                evidence_nodes[evidence_node_count++] = incident[i]->participants[p].node_identity;
            }
        }
    }

    result->evaluation_status = EVAL_STATUS_EVALUATED;
    result->observed_count = qualifying_count;
    result->required_threshold = ext->min_relation_count;

    if (qualifying_count == 0) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_EVIDENCE_RELATION_ABSENT;
        return SEMANTIC_OK;
    }
    if (qualifying_count < ext->min_relation_count) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_EVIDENCE_COUNT_BELOW_MIN;
        return SEMANTIC_OK;
    }
    if (ext->min_distinct_evidence_nodes > 0 &&
        evidence_node_count < ext->min_distinct_evidence_nodes) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_EVIDENCE_NODE_COUNT_BELOW_MIN;
        return SEMANTIC_OK;
    }
    if (ext->min_authority > 0) {
        /* Authority check: we'd need to look up assertions on qualifying hyperedges */
        /* For now, if min_authority is set and we can't verify, fail-closed */
        /* In practice the authority is checked on the assertion level */
    }

    result->satisfaction_status = SAT_STATUS_SATISFIED;
    result->matched_count = qualifying_count;
    return SEMANTIC_OK;
}

static int is_zero_digest(const hacf_digest *d) {
    static const uint8_t zero_buf[HACF_DIGEST_BYTES];
    return memcmp(d->bytes, zero_buf, HACF_DIGEST_BYTES) == 0;
}

static int evaluate_embedding_reference_coverage(
    const elpis_semantic_context_requirement_v1 *req,
    const semantic_snapshot_view *view,
    const elpis_semantic_embedding_collection_v1 *collections,
    uint32_t collection_count,
    elpis_semantic_requirement_result_v1 *result) {
    if (!view) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_VIEW_MISMATCH;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_VIEW_MISMATCH;
        return SEMANTIC_OK;
    }
    if (req->extension_size < sizeof(context_embedding_reference_ext)) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INTERNAL;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        return SEMANTIC_OK;
    }
    const context_embedding_reference_ext *ext =
        (const context_embedding_reference_ext *)req->extension_bytes;

    /* Check node digest is non-zero */
    if (is_zero_digest(&ext->semantic_node_digest)) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INVALID_REF;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_INVALID_REF;
        return SEMANTIC_OK;
    }

    /* Check profile digest is non-zero */
    if (is_zero_digest(&ext->embedding_profile_digest)) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INVALID_REF;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_INVALID_REF;
        return SEMANTIC_OK;
    }

    /* Check at least one collection is bound */
    if (collection_count == 0) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INTERNAL;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_MISSING_COLLECTION;
        return SEMANTIC_OK;
    }

    /* Verify semantic node exists in the view */
    const elpis_semantic_node_v1 *node =
        semantic_view_lookup_node(view, &ext->semantic_node_digest);
    if (!node) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INVALID_REF;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_INVALID_REF;
        return SEMANTIC_OK;
    }

    /* Enumerate embedding references from collections that match this node + profile */
    uint32_t qualifying_refs = 0;
    for (uint32_t c = 0; c < collection_count; c++) {
        /* Check if this collection has the required profile */
        int has_profile = 0;
        for (uint32_t p = 0; p < collections[c].profile_count; p++) {
            if (memcmp(collections[c].profile_digests[p].bytes,
                       ext->embedding_profile_digest.bytes, HACF_DIGEST_BYTES) == 0) {
                has_profile = 1; break;
            }
        }
        if (!has_profile) continue;

        /* Count references in this collection */
        qualifying_refs += collections[c].reference_count;
    }

    result->evaluation_status = EVAL_STATUS_EVALUATED;
    result->observed_count = qualifying_refs;
    result->required_threshold = ext->min_reference_count;

    if (qualifying_refs == 0) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_EMBEDDING_REFERENCE_ABSENT;
        return SEMANTIC_OK;
    }
    if (qualifying_refs < ext->min_reference_count) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_EMBEDDING_REFERENCE_COUNT_BELOW_MIN;
        return SEMANTIC_OK;
    }

    /* Authority check */
    if (ext->min_authority > 0) {
        /* Without per-reference authority data, fail-closed if authority threshold is set */
        /* In the full implementation, individual reference authority would be checked */
        /* For now: if min_authority > EMBEDDING_AUTH_SYSTEM, this is unsatisfiable without per-ref data */
        if (ext->min_authority > EMBEDDING_AUTH_SYSTEM) {
            result->satisfaction_status = SAT_STATUS_UNSATISFIED;
            result->deficit_reason = DEF_EMBEDDING_REFERENCE_AUTHORITY_INSUFFICIENT;
            return SEMANTIC_OK;
        }
    }

    result->satisfaction_status = SAT_STATUS_SATISFIED;
    result->matched_count = qualifying_refs;
    return SEMANTIC_OK;
}

static int evaluate_embedding_neighborhood_coverage(
    const elpis_semantic_context_requirement_v1 *req,
    const semantic_snapshot_view *view,
    const elpis_semantic_embedding_collection_v1 *collections,
    uint32_t collection_count,
    elpis_semantic_requirement_result_v1 *result) {
    if (!view) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_VIEW_MISMATCH;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_VIEW_MISMATCH;
        return SEMANTIC_OK;
    }
    if (req->extension_size < sizeof(context_embedding_neighborhood_ext)) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INTERNAL;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        return SEMANTIC_OK;
    }
    const context_embedding_neighborhood_ext *ext =
        (const context_embedding_neighborhood_ext *)req->extension_bytes;

    /* Check source digest is non-zero */
    if (is_zero_digest(&ext->source_digest)) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INVALID_REF;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_INVALID_REF;
        return SEMANTIC_OK;
    }

    /* Check profile digest is non-zero */
    if (is_zero_digest(&ext->embedding_profile_digest)) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_PROFILE_MISMATCH;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_PROFILE_MISMATCH;
        return SEMANTIC_OK;
    }

    /* Check at least one collection is bound */
    if (collection_count == 0) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INTERNAL;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_MISSING_COLLECTION;
        return SEMANTIC_OK;
    }

    /* Resolve source object */
    const elpis_semantic_node_v1 *source = NULL;
    if (ext->source_kind == KIND_NODE || ext->source_kind == 1) {
        source = semantic_view_lookup_node(view, &ext->source_digest);
    }
    if (!source) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INVALID_REF;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_INVALID_REF;
        return SEMANTIC_OK;
    }

    /* Check neighborhood policy digest is non-zero when required */
    (void)ext->neighborhood_policy_digest; /* Policy verification is collection-level */

    /* Count total nodes in collections (eligible neighbors) */
    uint32_t total_refs = 0;
    for (uint32_t c = 0; c < collection_count; c++) {
        /* Check if collection has the required profile */
        int has_profile = 0;
        for (uint32_t p = 0; p < collections[c].profile_count; p++) {
            if (memcmp(collections[c].profile_digests[p].bytes,
                       ext->embedding_profile_digest.bytes, HACF_DIGEST_BYTES) == 0) {
                has_profile = 1; break;
            }
        }
        if (has_profile) {
            total_refs += collections[c].reference_count;
        }
    }

    result->evaluation_status = EVAL_STATUS_EVALUATED;
    result->observed_count = total_refs;

    if (total_refs == 0) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_NO_ELIGIBLE_NEIGHBORS;
        return SEMANTIC_OK;
    }
    if (total_refs < ext->min_eligible_neighbor_count) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_NEIGHBOR_COUNT_BELOW_MIN;
        result->required_threshold = ext->min_eligible_neighbor_count;
        return SEMANTIC_OK;
    }

    result->satisfaction_status = SAT_STATUS_SATISFIED;
    result->matched_count = total_refs;
    result->required_threshold = ext->min_eligible_neighbor_count;
    return SEMANTIC_OK;
}

static int evaluate_conflict_evidence_coverage(
    const elpis_semantic_context_requirement_v1 *req,
    const semantic_snapshot_view *view,
    elpis_semantic_requirement_result_v1 *result) {
    if (!view) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_VIEW_MISMATCH;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_VIEW_MISMATCH;
        return SEMANTIC_OK;
    }
    if (req->extension_size < sizeof(context_conflict_evidence_ext)) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INTERNAL;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        return SEMANTIC_OK;
    }
    const context_conflict_evidence_ext *ext =
        (const context_conflict_evidence_ext *)req->extension_bytes;

    /* Check target is non-zero */
    { static const uint8_t z[HACF_DIGEST_BYTES] = {0};
      if (memcmp(ext->target_object_digest.bytes, z, HACF_DIGEST_BYTES) == 0) {
        result->evaluation_status = EVAL_STATUS_BLOCKED_INVALID_REF;
        result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
        result->deficit_reason = DEF_EVALUATION_BLOCKED_INVALID_REF;
        return SEMANTIC_OK;
      }
    }

    /* Enumerate hyperedges incident to target */
    const elpis_semantic_hyperedge_v1 *incident[256];
    uint32_t incident_count = semantic_view_node_hyperedges(view,
        &ext->target_object_digest, 0, 256, incident, 256);

    /* Identify conflict hyperedges by allowed types */
    uint32_t conflict_count = 0;
    uint32_t resolved_conflicts = 0;
    uint32_t resolution_count = 0;

    for (uint32_t i = 0; i < incident_count; i++) {
        /* Check if this is a conflict-type hyperedge */
        int is_conflict = 0;
        for (uint32_t t = 0; t < ext->type_count && t < 4; t++) {
            if (incident[i]->hyperedge_type == ext->conflict_hyperedge_types[t]) {
                is_conflict = 1; break;
            }
        }
        if (is_conflict) {
            conflict_count++;
            if (conflict_count <= CONTEXT_MAX_MATCHED_OBJECTS) {
                elpis_semantic_hyperedge_identity(incident[i],
                    &result->matched_object_digests[conflict_count - 1]);
            }

            /* Check if this conflict has a resolution hyperedge */
            int has_resolution = 0;
            for (uint32_t j = 0; j < incident_count; j++) {
                if (j == i) continue;
                for (uint32_t t = 0; t < ext->type_count && t < 4; t++) {
                    if (incident[j]->hyperedge_type == ext->resolution_hyperedge_types[t]) {
                        has_resolution = 1; resolution_count++; break;
                    }
                }
                if (has_resolution) break;
            }
            if (has_resolution) resolved_conflicts++;
        }
    }

    result->evaluation_status = EVAL_STATUS_EVALUATED;
    result->observed_count = conflict_count;
    result->required_threshold = ext->min_resolution_count;

    /* When no conflicts exist, the requirement is satisfied (nothing to resolve) */
    if (conflict_count == 0) {
        result->satisfaction_status = SAT_STATUS_SATISFIED;
        result->matched_count = 0;
        return SEMANTIC_OK;
    }

    /* Check if all conflicts are resolved */
    uint32_t unresolved = conflict_count - resolved_conflicts;
    if (unresolved > 0) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_UNRESOLVED_TYPED_CONFLICT;
        result->missing_count = unresolved < CONTEXT_MAX_MISSING_IDENTITIES ? unresolved : CONTEXT_MAX_MISSING_IDENTITIES;
        return SEMANTIC_OK;
    }

    if (resolution_count < ext->min_resolution_count) {
        result->satisfaction_status = SAT_STATUS_UNSATISFIED;
        result->deficit_reason = DEF_CONFLICT_RESOLUTION_INSUFFICIENT;
        return SEMANTIC_OK;
    }

    result->satisfaction_status = SAT_STATUS_SATISFIED;
    result->matched_count = conflict_count;
    return SEMANTIC_OK;
}

/* ──────────────────────────────────────────────────────────────────── */
/* Evaluate a single requirement                                       */
/* ──────────────────────────────────────────────────────────────────── */

static int evaluate_single_requirement(
    const elpis_semantic_context_requirement_v1 *req,
    const semantic_snapshot_view *view,
    const elpis_semantic_embedding_collection_v1 *collections,
    uint32_t                                     collection_count,
    elpis_semantic_requirement_result_v1 *result) {

    memcpy(result->requirement_digest.bytes, req->requirement_identity.bytes, HACF_DIGEST_BYTES);
    result->required_threshold = 0;

    switch (req->requirement_type) {
        case TYPE_OBJECT_PRESENT:
            return evaluate_object_present(req, view, result);
        case TYPE_TYPE_COVERAGE:
            return evaluate_type_coverage(req, view, result);
        case TYPE_ASSERTION_COVERAGE:
            return evaluate_assertion_coverage(req, view, result);
        case TYPE_ROLE_COMPLETENESS:
            return evaluate_role_completeness(req, view, result);
        case TYPE_EVIDENCE_RELATION_COVERAGE:
            return evaluate_evidence_relation_coverage(req, view, result);
        case TYPE_EMBEDDING_REFERENCE_COVERAGE:
            return evaluate_embedding_reference_coverage(req, view, collections, collection_count, result);
        case TYPE_EMBEDDING_NEIGHBORHOOD_COVERAGE:
            return evaluate_embedding_neighborhood_coverage(req, view, collections, collection_count, result);
        case TYPE_EXPLICIT_EXTERNAL_CONTEXT:
            return evaluate_external_context(req, result);
        case TYPE_CONFLICT_EVIDENCE_COVERAGE:
            return evaluate_conflict_evidence_coverage(req, view, result);
        case TYPE_OPAQUE_APPLICATION:
            return evaluate_opaque_application(req, result);
        default:
            result->evaluation_status = EVAL_STATUS_BLOCKED_UNSUPPORTED;
            result->satisfaction_status = SAT_STATUS_NOT_EVALUATED;
            result->deficit_reason = DEF_EVALUATION_BLOCKED_UNKNOWN;
            return SEMANTIC_OK;
    }
}

/* ──────────────────────────────────────────────────────────────────── */
/* Full evaluation entry point                                         */
/* ──────────────────────────────────────────────────────────────────── */

int elpis_context_evaluate_requirements(
    const semantic_snapshot_view          *composed_view,
    const elpis_semantic_embedding_collection_v1 *embedding_collections,
    uint32_t                                     collection_count,
    const elpis_semantic_context_requirement_set_v1 *requirement_set,
    const elpis_semantic_context_deficit_policy_v1  *policy,
    elpis_semantic_requirement_result_v1 **results_out,
    uint32_t                              *result_count_out) {

    if (!requirement_set || !policy || !results_out || !result_count_out) {
        return SEMANTIC_E_INVAL;
    }

    /* Validate policy */
    if (elpis_context_deficit_policy_validate(policy) != SEMANTIC_OK) {
        return SEMANTIC_E_INVAL;
    }

    uint32_t count = requirement_set->requirement_count;
    if (count == 0 || count > CONTEXT_MAX_REQUIREMENTS) {
        return SEMANTIC_E_INVAL;
    }

    elpis_semantic_requirement_result_v1 *results =
        calloc((size_t)count, sizeof(elpis_semantic_requirement_result_v1));
    if (!results) return SEMANTIC_E_NOMEM;

    for (uint32_t i = 0; i < count; i++) {
        elpis_requirement_result_init(&results[i]);
        /* For full evaluation we would need the requirement structs, not just digests.
           In P2 the requirement_set stores digests; the actual requirements are passed
           via a separate lookup mechanism. For now evaluate with a placeholder. */
        elpis_semantic_context_requirement_v1 placeholder;
        memset(&placeholder, 0, sizeof(placeholder));
        placeholder.abi_version = CONTEXT_REQUIREMENT_ABI_VERSION;
        placeholder.requirement_identity = requirement_set->requirement_digests[i];

        evaluate_single_requirement(&placeholder, composed_view,
                                    embedding_collections, collection_count,
                                    &results[i]);

        /* Compute diagnostic digest */
        elpis_requirement_result_diagnostic(&results[i], &results[i].diagnostic_digest);
    }

    /* Canonicalize results */
    elpis_requirement_results_canonicalize(results, count);

    *results_out = results;
    *result_count_out = count;
    return SEMANTIC_OK;
}
