#ifndef ELPIS_QUERY_LOCAL_PROPOSAL_H
#define ELPIS_QUERY_LOCAL_PROPOSAL_H

#include "elpis_semantic/query_overlay.h"
#include "elpis_semantic/type_registry.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ELPIS_QUERY_LOCAL_PROPOSAL_ABI_VERSION 1u
#define ELPIS_QUERY_LOCAL_PROPOSAL_NODE_TYPE 0x1000f200u
#define ELPIS_QUERY_LOCAL_PROPOSAL_STATUS_PROPOSED_UNADMITTED 1u
#define ELPIS_QUERY_LOCAL_REPRESENTATION_RECEIPT_ABI_VERSION 1u
#define ELPIS_QUERY_LOCAL_REPRESENTATION_RECEIPT_REPRESENTABLE 1u

typedef struct elpis_query_local_context_v1 {
    hacf_digest query_digest;
    hacf_digest proposal_digest;
    hacf_digest hacf_corpus_manifest_digest;
    hacf_digest hacf_context_graph_manifest_digest;
    hacf_digest registry_contract_digest;
    hacf_digest native_registry_digest;
    hacf_digest representation_policy_digest;
} elpis_query_local_context_v1;

typedef struct elpis_query_local_proposal_v1 {
    uint32_t abi_version;
    hacf_digest query_digest;
    hacf_digest proposal_digest;
    hacf_digest candidate_digest;
    hacf_digest hacf_corpus_manifest_digest;
    hacf_digest hacf_context_graph_manifest_digest;
    hacf_digest registry_contract_digest;
    hacf_digest native_registry_digest;
    hacf_digest representation_policy_digest;
    uint32_t candidate_status;
    uint32_t semantic_authority;
    uint32_t admission_authority;
    uint32_t execution_authority;
    uint32_t runtime_admission;
    hacf_digest envelope_identity;
    uint8_t reserved[32];
} elpis_query_local_proposal_v1;

typedef struct elpis_query_local_representation_receipt_v1 {
    uint32_t abi_version;
    hacf_digest envelope_identity;
    hacf_digest node_identity;
    hacf_digest assertion_identity;
    uint32_t disposition;
    uint32_t semantic_authority;
    uint32_t admission_authority;
    uint32_t execution_authority;
    uint32_t runtime_admission;
    hacf_digest receipt_identity;
    uint8_t reserved[32];
} elpis_query_local_representation_receipt_v1;

int elpis_query_local_proposal_identity(
    const elpis_query_local_proposal_v1 *proposal,
    hacf_digest *out);

int elpis_query_local_proposal_validate(
    const elpis_query_local_proposal_v1 *proposal,
    const elpis_query_local_context_v1 *expected);

int elpis_query_local_proposal_materialize(
    const elpis_query_local_proposal_v1 *proposal,
    const elpis_query_local_context_v1 *expected,
    elpis_semantic_node_v1 *node_out,
    elpis_semantic_assertion_v1 *assertion_out,
    elpis_query_local_representation_receipt_v1 *receipt_out);

int elpis_query_local_representation_receipt_validate(
    const elpis_query_local_representation_receipt_v1 *receipt);

int elpis_query_local_overlay_bind_context(
    semantic_query_overlay *overlay,
    const semantic_type_registry *registry,
    const elpis_query_local_context_v1 *context);

#ifdef __cplusplus
}
#endif
#endif
