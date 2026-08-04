/* elpis/hybrid_retrieval.h - deterministic lexical+dense fusion and bounded
 * one-hop contextual expansion (Gate R3). */
#ifndef ELPIS_HYBRID_RETRIEVAL_H
#define ELPIS_HYBRID_RETRIEVAL_H

#include <stdint.h>

#include "elpis/context_graph.h"
#include "elpis/corpus.h"
#include "elpis/retrieval_bundle.h"
#include "elpis/vector_index.h"

#ifdef __cplusplus
extern "C" {
#endif

#define ELPIS_HYBRID_ABI_VERSION 1u
#define ELPIS_HYBRID_SCORE_SCALE 1000000000ull
#define ELPIS_HYBRID_MAX_CANDIDATES 4096u
#define ELPIS_HYBRID_MAX_BUNDLE_ITEMS 256u

typedef enum elpis_hybrid_status {
    ELPIS_HYBRID_OK          =  0,
    ELPIS_HYBRID_E_INVAL     = -1,
    ELPIS_HYBRID_E_CORPUS    = -2,
    ELPIS_HYBRID_E_VECTOR    = -3,
    ELPIS_HYBRID_E_GRAPH     = -4,
    ELPIS_HYBRID_E_DRIFT     = -5,
    ELPIS_HYBRID_E_INTEGRITY = -6,
    ELPIS_HYBRID_E_LIMIT     = -7,
    ELPIS_HYBRID_E_INTERNAL  = -8
} elpis_hybrid_status;

typedef struct elpis_hybrid_error {
    int  status;
    int  cause;                  /* underlying elpis_vec_status, or 0 */
    char detail[192];
} elpis_hybrid_error;

typedef struct elpis_hybrid_policy {
    uint32_t abi_version;
    uint32_t lexical_limit;
    uint32_t dense_limit;
    uint32_t primary_limit;
    uint32_t graph_seed_limit;
    uint32_t graph_neighbors_per_seed;
    uint32_t total_limit;
    uint32_t rrf_k;
    uint32_t lexical_weight;
    uint32_t dense_weight;
    uint32_t min_graph_authority; /* hacf_authority 0..3 */
    uint32_t reserved[5];
} elpis_hybrid_policy;

typedef struct elpis_hybrid_query {
    const char  *text;             /* NUL-terminated, nonempty, <= 65535 bytes */
    const float *vector;
    uint32_t     dimensions;
    const char  *namespace_filter; /* NULL = all */
    const char  *authority_filter; /* NULL = all */
} elpis_hybrid_query;

typedef struct elpis_hybrid_retriever elpis_hybrid_retriever;

int elpis_hybrid_policy_default(elpis_hybrid_policy *out);
int elpis_hybrid_policy_validate(const elpis_hybrid_policy *p);
int elpis_hybrid_policy_digest(const elpis_hybrid_policy *p, char out[65]);

/* corpus, index and graph are borrowed and must outlive the retriever. graph may
 * be NULL. Creation captures corpus and index manifest identities. Every search
 * rechecks them and fails with E_DRIFT if either changed inside the epoch. */
int elpis_hybrid_retriever_create(elpis_corpus *corpus, elpis_vector_index *index,
                                  const elpis_context_graph *graph,
                                  const elpis_hybrid_policy *policy,
                                  elpis_hybrid_retriever **out);
void elpis_hybrid_retriever_destroy(elpis_hybrid_retriever *r);
const char *elpis_hybrid_retriever_error(const elpis_hybrid_retriever *r);
const elpis_hybrid_error *elpis_hybrid_retriever_last_error(const elpis_hybrid_retriever *r);

/* Produces one immutable bundle. RRF uses one-based source ranks:
 *   weight * ELPIS_HYBRID_SCORE_SCALE / (rrf_k + rank)
 * with integer division. Primary order is higher fused key then lower chunk
 * digest. Graph context is appended seed-rank first and never expands beyond
 * one hop. */
int elpis_hybrid_retrieve(elpis_hybrid_retriever *r, const elpis_hybrid_query *q,
                          elpis_retrieval_bundle **out);

const char *elpis_hybrid_strerror(int status);

#ifdef __cplusplus
}
#endif
#endif
