#ifndef ELPIS_SEMANTIC_TRM_ALIGNMENT_FIXTURE_H
#define ELPIS_SEMANTIC_TRM_ALIGNMENT_FIXTURE_H

#include <stdint.h>

#define TRM_FIXTURE_DIGEST_LEN 64
#define TRM_FIXTURE_CELL_COUNT 81
#define TRM_FIXTURE_SET_MAX 32

typedef enum {
    TRM_FIXTURE_SET_A = 0,  /* P10 production-representation */
    TRM_FIXTURE_SET_B = 1,  /* Native in-distribution */
    TRM_FIXTURE_SET_C = 2,  /* Placement-isolation */
} trm_fixture_set_id_t;

typedef struct {
    uint32_t ordinal;
    uint32_t clue_count;
    int8_t digits[TRM_FIXTURE_CELL_COUNT];
    int8_t fixed_mask[TRM_FIXTURE_CELL_COUNT];
    int8_t solution[TRM_FIXTURE_CELL_COUNT];
    char fixture_digest[TRM_FIXTURE_DIGEST_LEN];
    char reference_digest[TRM_FIXTURE_DIGEST_LEN];
    trm_fixture_set_id_t set_id;
} trm_fixture_t;

typedef struct {
    trm_fixture_t fixtures[TRM_FIXTURE_SET_MAX];
    uint32_t fixture_count;
    trm_fixture_set_id_t set_id;
    char set_digest[TRM_FIXTURE_DIGEST_LEN];
    int sealed_before_execution;
} trm_fixture_set_t;

trm_fixture_set_t trm_fixture_set_create(trm_fixture_set_id_t set_id);
int trm_fixture_add(trm_fixture_set_t *set, trm_fixture_t fixture);
int trm_fixture_set_seal(trm_fixture_set_t *set);
int trm_fixture_set_is_sealed(const trm_fixture_set_t *set);
int trm_fixture_is_sudoku_valid(const int8_t digits[TRM_FIXTURE_CELL_COUNT]);
int trm_fixture_count_correct(const int8_t board[TRM_FIXTURE_CELL_COUNT],
                               const int8_t solution[TRM_FIXTURE_CELL_COUNT]);
int trm_fixture_count_wrong(const int8_t board[TRM_FIXTURE_CELL_COUNT],
                             const int8_t solution[TRM_FIXTURE_CELL_COUNT]);
void trm_fixture_compute_digest(const trm_fixture_t *fixture);
void trm_fixture_set_compute_digest(const trm_fixture_set_t *set);

#endif
