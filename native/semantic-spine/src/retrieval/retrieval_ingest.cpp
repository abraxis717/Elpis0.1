/* retrieval_ingest.cpp — Evidence ingestion from RetrievalBundle.
 *
 * For each admitted RetrievalBundle item:
 *   - Verify authority meets P2 minimum floor
 *   - Create/reuse EVIDENCE_CHUNK semantic node (by chunk digest)
 *   - Create assertion with RetrievalBundle HACF package provenance
 *   - Create immutable retrieval item attachment
 *   - Create RETRIEVED_FOR transport hyperedge
 *   - Create DERIVED_FROM_RETRIEVAL_BUNDLE transport hyperedge
 *   - For context items: RETRIEVAL_CONTEXT_EXPANSION hyperedge
 *
 * P3 does NOT create: SUPPORTS, CONTRADICTS, CAUSES, REQUIRES, SAME_AS, EQUIVALENT_TO.
 * P3 does NOT infer semantic truth.
 */
#include "elpis_semantic/retrieval_ingest.h"
#include "elpis_semantic/retrieval_item_attachment.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/retrieval_requirement.h"
#include "elpis_semantic/type_registry.h"
#include "elpis/retrieval_bundle.h"
#include "elpis/sha256.h"
#include "elpis/cascade.h"

#include <cstring>
#include <cstdint>
#include <set>
#include <string>

namespace {

static const char kZeroDigest[] =
    "0000000000000000000000000000000000000000000000000000000000000000";

/* Map R3 authority string to numeric value */
static uint32_t authority_string_to_numeric(const char *authority_str) {
    if (!authority_str) return 0;
    if (std::strcmp(authority_str, "canonical") == 0) return HACF_AUTH_CANONICAL;
    if (std::strcmp(authority_str, "reference") == 0) return HACF_AUTH_REFERENCE;
    if (std::strcmp(authority_str, "advisory") == 0) return HACF_AUTH_ADVISORY;
    if (std::strcmp(authority_str, "provisional") == 0) return HACF_AUTH_ADVISORY;
    return 0; /* advisory as default */
}

} // namespace

extern "C" {

void elpis_retrieval_ingest_init(elpis_retrieval_ingest_result_v1 *result) {
    if (!result) return;
    std::memset(result, 0, sizeof(*result));
    result->abi_version = RETRIEVAL_INGEST_ABI_VERSION;
}

int elpis_retrieval_ingest(
    elpis_retrieval_ingest_result_v1 *result,
    ingest_item_result *items_out,
    uint32_t items_capacity,
    elpis_retrieval_bundle *bundle,
    const elpis_semantic_retrieval_requirement_v1 *requirement,
    const semantic_type_registry *type_registry,
    uint32_t authority_floor)
{
    if (!result || !items_out || !bundle || !requirement || !type_registry)
        return SEMANTIC_E_INVAL;

    elpis_retrieval_ingest_init(result);

    /* Get bundle identity for provenance */
    char qd[65], cd[65], vd[65], gd[65], pd[65], bd[65], hd[65];
    if (elpis_retrieval_bundle_identity(bundle, qd, cd, vd, gd, pd, bd, hd) != 0)
        return SEMANTIC_E_INVAL;

    hacf_digest bundle_pkg_digest;
    if (hacf_digest_from_hex(hd, &bundle_pkg_digest) != 0)
        return SEMANTIC_E_INVAL;

    result->bundle_package_digest = bundle_pkg_digest;

    /* Requirement digest */
    hacf_digest req_digest;
    if (elpis_retrieval_requirement_identity(requirement, &req_digest) != 0)
        return SEMANTIC_E_INVAL;
    result->requirement_digest = req_digest;

    /* Bundle digest */
    hacf_digest bundle_d;
    if (hacf_digest_from_hex(bd, &bundle_d) != 0)
        return SEMANTIC_E_INVAL;
    result->bundle_digest = bundle_d;

    uint32_t count = elpis_retrieval_bundle_item_count(bundle);
    if (count > items_capacity)
        return SEMANTIC_E_INVAL;

    result->total_items = count;

    /* Track admitted primary parents for context item validation */
    std::set<std::string> admitted_primary_parents;

    for (uint32_t i = 0; i < count; ++i) {
        elpis_retrieval_item_view view;
        if (elpis_retrieval_bundle_item(bundle, i, &view) != 0) {
            items_out[i].status = INGEST_INTERNAL_ERROR;
            items_out[i].item_index = i;
            result->rejected_count++;
            continue;
        }

        std::memset(&items_out[i], 0, sizeof(items_out[i]));
        items_out[i].item_index = i;

        /* Step 1: Verify authority meets P2 minimum floor */
        uint32_t item_auth = authority_string_to_numeric(view.authority);
        if (item_auth < authority_floor) {
            items_out[i].status = INGEST_AUTHORITY_REJECTED;
            result->rejected_count++;
            continue;
        }

        /* Step 2: Context parent validation */
        if (view.item_kind == ELPIS_RITEM_CONTEXT) {
            if (admitted_primary_parents.find(view.graph_parent_digest) ==
                admitted_primary_parents.end()) {
                items_out[i].status = INGEST_CONTEXT_PARENT_MISSING;
                result->rejected_count++;
                continue;
            }
        }

        /* Step 2: Create EVIDENCE_CHUNK node (identity = chunk_digest) */
        /* Node type: EVIDENCE_CHUNK (use node type from registry) */
        elpis_semantic_node_v1 *node = &items_out[i].evidence_node;
        std::memset(node, 0, sizeof(*node));
        node->abi_version = SEMANTIC_ABI_VERSION;
        /* Find EVIDENCE_CHUNK type in registry */
        /* We use the type from the registry extension */
        const semantic_node_type_entry *chunk_type =
            semantic_type_registry_get_node_type(type_registry,
                SEMANTIC_NODE_NAMESPACE | 10); /* EVIDENCE_CHUNK type */
        if (chunk_type)
            node->node_type = chunk_type->node_type;
        else
            node->node_type = SEMANTIC_NODE_NAMESPACE | 10; /* fallback */
        node->semantic_flags = SEMANTIC_NODE_FLAG_EXTERNAL;

        /* Payload digest = chunk_digest (hex string -> binary) */
        hacf_digest chunk_d;
        if (hacf_digest_from_hex(view.chunk_digest, &chunk_d) != 0) {
            items_out[i].status = INGEST_INTERNAL_ERROR;
            result->rejected_count++;
            continue;
        }
        node->payload_digest = chunk_d;

        /* Compute node identity */
        if (elpis_semantic_node_identity(node, &node->node_identity) != SEMANTIC_OK) {
            items_out[i].status = INGEST_INTERNAL_ERROR;
            result->rejected_count++;
            continue;
        }

        /* Step 3: Create assertion with bundle HACF package provenance */
        elpis_semantic_assertion_v1 *assertion = &items_out[i].assertion;
        std::memset(assertion, 0, sizeof(*assertion));
        assertion->abi_version = SEMANTIC_ABI_VERSION;
        assertion->asserted_object_kind = SEMANTIC_OBJECT_KIND_NODE;
        assertion->asserted_object_digest = node->node_identity;
        assertion->provenance_digest = bundle_pkg_digest;
        assertion->authority = item_auth;
        assertion->assertion_flags = SEMANTIC_ASSERTION_FLAG_NONE;

        if (elpis_semantic_assertion_identity(assertion, &assertion->assertion_identity)
            != SEMANTIC_OK) {
            items_out[i].status = INGEST_INTERNAL_ERROR;
            result->rejected_count++;
            continue;
        }

        /* Step 4: Create attachment */
        elpis_retrieval_item_attachment_v1 *att = &items_out[i].attachment;
        elpis_attachment_init(att);

        att->evidence_node_digest = node->node_identity;
        att->retrieval_bundle_digest = bundle_d;
        att->retrieval_bundle_package_digest = bundle_pkg_digest;
        att->retrieval_requirement_digest = req_digest;

        hacf_digest chunk_dig, doc_dig, text_dig, ns_dig;
        hacf_digest_from_hex(view.chunk_digest, &chunk_dig);
        hacf_digest_from_hex(view.doc_digest, &doc_dig);
        hacf_digest_from_hex(view.text_digest, &text_dig);

        /* Namespace digest: compute from ns string bytes */
        std::memset(&ns_dig, 0, sizeof(ns_dig));
        if (view.ns && view.ns[0] != '\0') {
            uint8_t ns_hash[32];
            size_t ns_len = strnlen(view.ns, 96);
            elpis_sha256(view.ns, ns_len, ns_hash);
            std::memcpy(ns_dig.bytes, ns_hash, 32);
        }

        att->chunk_digest = chunk_dig;
        att->document_digest = doc_dig;
        att->text_digest = text_dig;
        att->namespace_digest = ns_dig;
        att->item_authority = item_auth;
        att->source_mask = view.source_mask;
        att->lexical_rank = view.lexical_rank;
        att->dense_rank = view.dense_rank;
        att->dense_score_key = view.dense_score_key;
        att->fusion_score_key = view.fusion_score_key;
        att->final_rank = view.final_rank;
        att->item_kind = view.item_kind;

        /* Graph metadata */
        if (view.item_kind == ELPIS_RITEM_CONTEXT && view.graph_parent_digest[0] != '\0') {
            hacf_digest parent_dig;
            if (hacf_digest_from_hex(view.graph_parent_digest, &parent_dig) == 0) {
                att->graph_parent_digest = parent_dig;
                att->graph_hop = view.graph_hop;
                att->graph_edge_type = view.edge_type;
                att->graph_edge_authority = view.edge_authority;
                /* Graph edge provenance: R3 omits exact provenance */
                att->graph_edge_provenance_status = GRAPH_PROVENANCE_UNAVAILABLE;
            }
        } else {
            std::memset(&att->graph_parent_digest, 0, sizeof(att->graph_parent_digest));
            att->graph_hop = 0;
            att->graph_edge_provenance_status = GRAPH_PROVENANCE_NOT_APPLICABLE;
        }

        /* Compute attachment digest */
        if (elpis_attachment_digest(att, &att->attachment_digest) != SEMANTIC_OK) {
            items_out[i].status = INGEST_INTERNAL_ERROR;
            result->rejected_count++;
            continue;
        }

        /* Step 5: Create RETRIEVED_FOR transport hyperedge */
        elpis_semantic_hyperedge_v1 *rf_edge = &items_out[i].retrieved_for_edge;
        std::memset(rf_edge, 0, sizeof(*rf_edge));
        rf_edge->abi_version = SEMANTIC_ABI_VERSION;
        rf_edge->hyperedge_type = SEMANTIC_HYPEREDGE_NAMESPACE | 10; /* RETRIEVED_FOR */
        rf_edge->semantic_flags = SEMANTIC_HYPEREDGE_FLAG_NONE;
        rf_edge->participant_count = 2;

        rf_edge->participants[0].node_identity = node->node_identity;
        rf_edge->participants[0].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 10; /* EVIDENCE */
        rf_edge->participants[0].ordinal = 0;

        rf_edge->participants[1].node_identity = req_digest;
        rf_edge->participants[1].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 7; /* REQUIREMENT */
        rf_edge->participants[1].ordinal = 1;

        /* Compute hyperedge identity */
        elpis_semantic_canonicalize_participants(rf_edge->participants, 2);
        if (elpis_semantic_hyperedge_identity(rf_edge, &rf_edge->hyperedge_identity)
            != SEMANTIC_OK) {
            items_out[i].status = INGEST_INTERNAL_ERROR;
            result->rejected_count++;
            continue;
        }

        /* Step 6: Create DERIVED_FROM_RETRIEVAL_BUNDLE hyperedge */
        elpis_semantic_hyperedge_v1 *dab_edge = &items_out[i].derived_from_bundle_edge;
        std::memset(dab_edge, 0, sizeof(*dab_edge));
        dab_edge->abi_version = SEMANTIC_ABI_VERSION;
        dab_edge->hyperedge_type = SEMANTIC_HYPEREDGE_NAMESPACE | 11; /* DERIVED_FROM_BUNDLE */
        dab_edge->semantic_flags = SEMANTIC_HYPEREDGE_FLAG_NONE;
        dab_edge->participant_count = 2;

        dab_edge->participants[0].node_identity = node->node_identity;
        dab_edge->participants[0].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 10; /* EVIDENCE */
        dab_edge->participants[0].ordinal = 0;

        dab_edge->participants[1].node_identity = bundle_d;
        dab_edge->participants[1].incidence_role = SEMANTIC_INCIDENCE_NAMESPACE | 8; /* BUNDLE */
        dab_edge->participants[1].ordinal = 1;

        elpis_semantic_canonicalize_participants(dab_edge->participants, 2);
        if (elpis_semantic_hyperedge_identity(dab_edge, &dab_edge->hyperedge_identity)
            != SEMANTIC_OK) {
            items_out[i].status = INGEST_INTERNAL_ERROR;
            result->rejected_count++;
            continue;
        }

        /* Step 7: Admitted — track for context parent validation */
        items_out[i].status = INGEST_ADMITTED;
        result->admitted_count++;

        if (view.item_kind == ELPIS_RITEM_PRIMARY) {
            admitted_primary_parents.insert(view.chunk_digest);
        }
    }

    return SEMANTIC_OK;
}

} // extern "C"
