#ifndef ELPIS_REGEX_HACF_QUERY_INGRESS_H
#define ELPIS_REGEX_HACF_QUERY_INGRESS_H

#include <stddef.h>
#include <stdint.h>

#include "elpis/corpus.h"
#include "elpis/context_graph.h"

#if defined(__GNUC__) || defined(__clang__)
#define ELPIS_REGEX_HACF_QUERY_INGRESS_API __attribute__((visibility("default")))
#else
#define ELPIS_REGEX_HACF_QUERY_INGRESS_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define ELPIS_REGEX_HACF_QUERY_INGRESS_ABI_VERSION_V1 1u

#define ELPIS_REGEX_HACF_QUERY_INGRESS_OK 0
#define ELPIS_REGEX_HACF_QUERY_INGRESS_E_INVAL (-1)
#define ELPIS_REGEX_HACF_QUERY_INGRESS_E_REGEX (-2)
#define ELPIS_REGEX_HACF_QUERY_INGRESS_E_HACF (-3)
#define ELPIS_REGEX_HACF_QUERY_INGRESS_E_BATCH (-4)
#define ELPIS_REGEX_HACF_QUERY_INGRESS_E_NOMEM (-5)
#define ELPIS_REGEX_HACF_QUERY_INGRESS_E_RANGE (-6)
#define ELPIS_REGEX_HACF_QUERY_INGRESS_E_CARDINALITY (-7)

typedef struct elpis_regex_hacf_query_ingress_result_v1
    elpis_regex_hacf_query_ingress_result_v1;

typedef struct elpis_regex_hacf_query_ingress_candidate_view_v1 {
    uint32_t abi_version;
    char candidate_id[65];
    uint8_t reserved[32];
} elpis_regex_hacf_query_ingress_candidate_view_v1;

ELPIS_REGEX_HACF_QUERY_INGRESS_API
uint32_t elpis_regex_hacf_query_ingress_abi_version_v1(void);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
int elpis_regex_hacf_query_ingress_run_v1(
    const uint8_t *task_bytes,
    size_t task_len,
    size_t regex_chunk_size,
    elpis_corpus *corpus,
    elpis_context_graph *context_graph,
    elpis_regex_hacf_query_ingress_result_v1 **out);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
void elpis_regex_hacf_query_ingress_result_destroy_v1(
    elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
const char *elpis_regex_hacf_query_ingress_result_status_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
const char *elpis_regex_hacf_query_ingress_result_source_sha256_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
const char *elpis_regex_hacf_query_ingress_result_proposal_digest_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
const char *elpis_regex_hacf_query_ingress_result_corpus_manifest_digest_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
const char *elpis_regex_hacf_query_ingress_result_context_graph_manifest_digest_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
const char *elpis_regex_hacf_query_ingress_result_proposal_set_digest_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
const char *elpis_regex_hacf_query_ingress_result_query_local_segment_digest_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
const char *elpis_regex_hacf_query_ingress_result_overlay_identity_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
const char *elpis_regex_hacf_query_ingress_result_batch_receipt_identity_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
const char *elpis_regex_hacf_query_ingress_result_proposal_json_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
uint32_t elpis_regex_hacf_query_ingress_result_candidate_count_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
int elpis_regex_hacf_query_ingress_result_candidate_at_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result,
    uint32_t index,
    elpis_regex_hacf_query_ingress_candidate_view_v1 *out);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
int elpis_regex_hacf_query_ingress_result_fail_closed_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
int elpis_regex_hacf_query_ingress_result_batch_published_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
int elpis_regex_hacf_query_ingress_result_semantic_authority_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
int elpis_regex_hacf_query_ingress_result_admission_authority_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
int elpis_regex_hacf_query_ingress_result_execution_authority_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
int elpis_regex_hacf_query_ingress_result_runtime_admission_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result);

ELPIS_REGEX_HACF_QUERY_INGRESS_API
const char *elpis_regex_hacf_query_ingress_last_error_v1(void);

#ifdef __cplusplus
}
#endif

#endif
