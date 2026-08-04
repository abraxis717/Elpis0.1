#include "elpis_semantic/trm_alignment_fixture.h"
#include <string.h>
#include <stdio.h>
#include <openssl/sha.h>

static void sha256_hex(const void *data, size_t len, char *out, size_t out_len) {
    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256(data, len, hash);
    for (int i = 0; i < SHA256_DIGEST_LENGTH && (size_t)(i * 2 + 2) < out_len; i++) {
        sprintf(out + i * 2, "%02x", hash[i]);
    }
}

trm_fixture_set_t trm_fixture_set_create(trm_fixture_set_id_t set_id) {
    trm_fixture_set_t set;
    memset(&set, 0, sizeof(set));
    set.set_id = set_id;
    set.fixture_count = 0;
    set.sealed_before_execution = 0;
    return set;
}

int trm_fixture_add(trm_fixture_set_t *set, trm_fixture_t fixture) {
    if (!set || set->fixture_count >= TRM_FIXTURE_SET_MAX) return 0;
    if (set->sealed_before_execution) return 0;
    set->fixtures[set->fixture_count++] = fixture;
    return 1;
}

int trm_fixture_set_seal(trm_fixture_set_t *set) {
    if (!set) return 0;
    set->sealed_before_execution = 1;
    trm_fixture_set_compute_digest(set);
    return 1;
}

int trm_fixture_set_is_sealed(const trm_fixture_set_t *set) {
    return set ? set->sealed_before_execution : 0;
}

int trm_fixture_is_sudoku_valid(const int8_t digits[TRM_FIXTURE_CELL_COUNT]) {
    // Check rows
    for (int r = 0; r < 9; r++) {
        int seen[10] = {0};
        for (int c = 0; c < 9; c++) {
            int d = digits[r * 9 + c];
            if (d == 0) continue;
            if (d < 1 || d > 9) return 0;
            if (seen[d]) return 0;
            seen[d] = 1;
        }
    }
    // Check columns
    for (int c = 0; c < 9; c++) {
        int seen[10] = {0};
        for (int r = 0; r < 9; r++) {
            int d = digits[r * 9 + c];
            if (d == 0) continue;
            if (seen[d]) return 0;
            seen[d] = 1;
        }
    }
    // Check 3x3 boxes
    for (int br = 0; br < 3; br++) {
        for (int bc = 0; bc < 3; bc++) {
            int seen[10] = {0};
            for (int r = br * 3; r < (br + 1) * 3; r++) {
                for (int c = bc * 3; c < (bc + 1) * 3; c++) {
                    int d = digits[r * 9 + c];
                    if (d == 0) continue;
                    if (seen[d]) return 0;
                    seen[d] = 1;
                }
            }
        }
    }
    return 1;
}

int trm_fixture_count_correct(const int8_t board[TRM_FIXTURE_CELL_COUNT],
                               const int8_t solution[TRM_FIXTURE_CELL_COUNT]) {
    int count = 0;
    for (int i = 0; i < TRM_FIXTURE_CELL_COUNT; i++) {
        if (board[i] == solution[i]) count++;
    }
    return count;
}

int trm_fixture_count_wrong(const int8_t board[TRM_FIXTURE_CELL_COUNT],
                             const int8_t solution[TRM_FIXTURE_CELL_COUNT]) {
    int count = 0;
    for (int i = 0; i < TRM_FIXTURE_CELL_COUNT; i++) {
        if (board[i] != 0 && board[i] != solution[i]) count++;
    }
    return count;
}

void trm_fixture_compute_digest(const trm_fixture_t *fixture) {
    if (!fixture) return;
    sha256_hex(fixture->digits, TRM_FIXTURE_CELL_COUNT,
               fixture->fixture_digest, TRM_FIXTURE_DIGEST_LEN);
}

void trm_fixture_set_compute_digest(const trm_fixture_set_t *set) {
    if (!set) return;
    sha256_hex(set->fixtures, set->fixture_count * sizeof(trm_fixture_t),
               set->set_digest, TRM_FIXTURE_DIGEST_LEN);
}
