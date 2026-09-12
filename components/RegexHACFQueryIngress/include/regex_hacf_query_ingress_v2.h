#ifndef ELPIS_REGEX_HACF_QUERY_INGRESS_V2_H
#define ELPIS_REGEX_HACF_QUERY_INGRESS_V2_H
#include "regex_hacf_query_ingress.h"
#include "streaming_regex_ingress_v2.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Borrows a finalized immutable Regex result for the duration of this call.
 * Accepts V1 and V2-produced results. Does not parse source again. Output uses
 * the existing result/accessor/ownership contract. All authority stays zero;
 * ambiguity still rejects before atomic query-local batch construction.
 */
ELPIS_REGEX_HACF_QUERY_INGRESS_API
int elpis_regex_hacf_query_ingress_from_regex_result_v2(
    const elpis_streaming_regex_result_v1* regex,
    elpis_corpus* corpus, elpis_context_graph* context_graph,
    elpis_regex_hacf_query_ingress_result_v1** out);
#ifdef __cplusplus
}
#endif
#endif
