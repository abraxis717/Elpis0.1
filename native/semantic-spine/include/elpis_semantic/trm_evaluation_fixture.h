/* elpis_semantic/trm_evaluation_fixture.h — P10 evaluation fixture v1.
 *
 * Single evaluation fixture binding input board, masks, reference solution,
 * and uniqueness receipt.
 * Identity domain: "elpis.semantic.trm_evaluation_fixture.v1"
 */
#ifndef ELPIS_SEMANTIC_TRM_EVALUATION_FIXTURE_H
#define ELPIS_SEMANTIC_TRM_EVALUATION_FIXTURE_H

#include "elpis_semantic/grid81_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define TRM_EVALUATION_FIXTURE_VERSION 1u

typedef enum trm_fixture_uniqueness {
    TRM_FIXTURE_NO_SOLUTION = 0u,
    TRM_FIXTURE_EXACTLY_ONE_SOLUTION = 1u,
    TRM_FIXTURE_MULTIPLE_SOLUTIONS = 2u,
} trm_fixture_uniqueness;

typedef struct elpis_semantic_trm_evaluation_fixture_v1 {
    uint32_t                          abi_version;
    uint32_t                          fixture_ordinal;
    uint32_t                          clue_stratum;
    uint32_t                          clue_count;

    /* Input board */
    uint32_t                          input_digits[GRID81_CELL_COUNT];
    uint32_t                          fixed_mask[GRID81_CELL_COUNT];
    uint32_t                          writable_mask[GRID81_CELL_COUNT];

    /* Reference solution */
    uint32_t                          reference_digits[GRID81_CELL_COUNT];

    /* Input digit classes [cell][class] */
    uint32_t                          input_digit_classes
        [GRID81_CELL_COUNT][GRID81_DIGIT_CLASS_COUNT];

    /* Uniqueness receipt */
    uint32_t                          uniqueness_result; /* trm_fixture_uniqueness */

    /* Digests */
    hacf_digest                       fixture_digest;
    hacf_digest                       input_digest;
    hacf_digest                       clue_mask_digest;
    hacf_digest                       reference_digest;

    uint8_t                           reserved[64];
} elpis_semantic_trm_evaluation_fixture_v1;

void elpis_trm_evaluation_fixture_init(
    elpis_semantic_trm_evaluation_fixture_v1 *fixture,
    uint32_t ordinal);

int elpis_trm_evaluation_fixture_identity(
    const elpis_semantic_trm_evaluation_fixture_v1 *fixture,
    hacf_digest *out);

int elpis_trm_evaluation_fixture_validate(
    const elpis_semantic_trm_evaluation_fixture_v1 *fixture);

int elpis_write_trm_evaluation_fixture(const char *path,
    const elpis_semantic_trm_evaluation_fixture_v1 *fixture);
int elpis_read_trm_evaluation_fixture(const char *path,
    elpis_semantic_trm_evaluation_fixture_v1 *out);

#ifdef __cplusplus
}
#endif
#endif
