/* elpis_semantic/trm_evaluation_corpus.h — P10 evaluation corpus v1.
 *
 * Collection of evaluation fixtures with sealed pre-execution identity.
 * Identity domain: "elpis.semantic.trm_evaluation_corpus.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_EVALUATION_CORPUS_H
#define ELPIS_SEMANTIC_TRM_EVALUATION_CORPUS_H

#include "elpis_semantic/trm_evaluation_fixture.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_EVALUATION_CORPUS_VERSION 1u
#define TRM_EVALUATION_CORPUS_FIXTURE_COUNT 16u

typedef struct elpis_semantic_trm_evaluation_corpus_v1 {
    uint32_t                          abi_version;
    uint32_t                          fixture_count;

    /* Fixture digests (in ordinal order) */
    hacf_digest                       fixture_digests[TRM_EVALUATION_CORPUS_FIXTURE_COUNT];

    /* Reference solution digests */
    hacf_digest                       reference_digests[TRM_EVALUATION_CORPUS_FIXTURE_COUNT];

    /* Clue stratum mapping: fixture_ordinal -> stratum index */
    uint32_t                          fixture_stratum[TRM_EVALUATION_CORPUS_FIXTURE_COUNT];

    /* Seal */
    hacf_digest                       corpus_manifest_digest;
    hacf_digest                       generation_trace_digest;
    uint32_t                          pre_execution_sealed; /* 1=sealed */

    uint8_t                           reserved[128];
} elpis_semantic_trm_evaluation_corpus_v1;

void elpis_trm_evaluation_corpus_init(
    elpis_semantic_trm_evaluation_corpus_v1 *corpus);

int elpis_trm_evaluation_corpus_identity(
    const elpis_semantic_trm_evaluation_corpus_v1 *corpus,
    hacf_digest *out);

int elpis_trm_evaluation_corpus_validate(
    const elpis_semantic_trm_evaluation_corpus_v1 *corpus);

int elpis_write_trm_evaluation_corpus(const char *path,
    const elpis_semantic_trm_evaluation_corpus_v1 *corpus);
int elpis_read_trm_evaluation_corpus(const char *path,
    elpis_semantic_trm_evaluation_corpus_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
