#ifndef ELPIS_QUERY_LOCAL_PROPOSAL_BATCH_H
#define ELPIS_QUERY_LOCAL_PROPOSAL_BATCH_H

#include "query_local_proposal.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define ELPIS_QUERY_LOCAL_PROPOSAL_BATCH_ABI_VERSION 1u
#define ELPIS_QUERY_LOCAL_PROPOSAL_BATCH_RECEIPT_ABI_VERSION 1u
#define ELPIS_QUERY_LOCAL_PROPOSAL_BATCH_RECEIPT_COMMITTED 1u
#define ELPIS_QUERY_LOCAL_PROPOSAL_MAX_BATCH 256u

typedef struct elpis_query_local_proposal_batch_receipt_v1 {
    uint32_t abi_version;
    hacf_digest query_digest;
    hacf_digest proposal_digest;
    hacf_digest proposal_set_digest;
    uint32_t proposal_count;
    hacf_digest registry_contract_digest;
    hacf_digest native_registry_digest;
    hacf_digest representation_policy_digest;
    hacf_digest hacf_corpus_manifest_digest;
    hacf_digest hacf_context_graph_manifest_digest;
    hacf_digest overlay_identity;
    uint32_t disposition;
    uint32_t semantic_authority;
    uint32_t admission_authority;
    uint32_t execution_authority;
    uint32_t runtime_admission;
    hacf_digest receipt_identity;
    uint8_t reserved[32];
} elpis_query_local_proposal_batch_receipt_v1;

int elpis_query_local_proposal_set_digest(
    const elpis_query_local_proposal_v1 *proposals,
    uint32_t proposal_count,
    hacf_digest *out);

int elpis_query_local_proposal_batch_receipt_validate(
    const elpis_query_local_proposal_batch_receipt_v1 *receipt);

int elpis_query_local_proposal_batch_build_overlay(
    const semantic_snapshot_manifest *base_manifest,
    const semantic_type_registry *registry,
    const elpis_query_local_context_v1 *context,
    const elpis_query_local_proposal_v1 *proposals,
    uint32_t proposal_count,
    semantic_query_overlay **overlay_out,
    elpis_query_local_proposal_batch_receipt_v1 *receipt_out);

#ifdef __cplusplus
}
#endif
#endif
