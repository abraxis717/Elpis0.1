/* trm_structural_delta.c — Categorical structural delta implementation. */
#include "elpis_semantic/trm_structural_delta.h"
#include <stdio.h>
#include <string.h>

void elpis_trm_structural_delta_init(
    elpis_semantic_trm_structural_delta_v1 *delta) {
    memset(delta, 0, sizeof(*delta));
    delta->abi_version = TRM_STRUCTURAL_DELTA_VERSION;
}

int elpis_trm_structural_delta_compute(
    elpis_semantic_trm_structural_delta_v1 *delta,
    const uint32_t before[GRID81_CELL_COUNT],
    const uint32_t after[GRID81_CELL_COUNT],
    const uint32_t reference[GRID81_CELL_COUNT],
    const uint32_t fixed_mask[GRID81_CELL_COUNT],
    trm_delta_scope scope,
    uint32_t step_index) {
    delta->delta_scope = scope;
    delta->step_index = step_index;

    memcpy(delta->before_digits, before, sizeof(uint32_t) * GRID81_CELL_COUNT);
    memcpy(delta->after_digits, after, sizeof(uint32_t) * GRID81_CELL_COUNT);
    memcpy(delta->reference_digits, reference, sizeof(uint32_t) * GRID81_CELL_COUNT);

    uint32_t changed_count = 0;
    uint32_t correct_add = 0, wrong_add = 0, corr = 0, regr = 0;
    uint32_t wrong_diff = 0, unch_correct = 0, unch_wrong = 0, unch_empty = 0;

    for (uint32_t c = 0; c < GRID81_CELL_COUNT; c++) {
        uint32_t b = before[c], a = after[c], ref = reference[c];

        int b_correct = (b != 0 && b == ref);
        int b_wrong = (b != 0 && b != ref);
        int b_empty = (b == 0);
        int a_correct = (a != 0 && a == ref);
        int a_wrong = (a != 0 && a != ref);
        int a_empty = (a == 0);

        delta->correct_before_mask[c] = b_correct ? 1 : 0;
        delta->correct_after_mask[c] = a_correct ? 1 : 0;
        delta->wrong_before_mask[c] = b_wrong ? 1 : 0;
        delta->wrong_after_mask[c] = a_wrong ? 1 : 0;

        if (b_empty && a_correct) {
            delta->transition_class[c] = TRM_TRANSITION_EMPTY_TO_CORRECT;
            correct_add++; delta->changed_mask[c] = 1;
        } else if (b_empty && a_wrong) {
            delta->transition_class[c] = TRM_TRANSITION_EMPTY_TO_WRONG;
            wrong_add++; delta->changed_mask[c] = 1;
        } else if (b_wrong && a_correct) {
            delta->transition_class[c] = TRM_TRANSITION_WRONG_TO_CORRECT;
            corr++; delta->changed_mask[c] = 1;
        } else if (b_correct && a_wrong) {
            delta->transition_class[c] = TRM_TRANSITION_CORRECT_TO_WRONG;
            regr++; delta->changed_mask[c] = 1;
        } else if (b_wrong && a_wrong && b != a) {
            delta->transition_class[c] = TRM_TRANSITION_WRONG_TO_DIFFERENT_WRONG;
            wrong_diff++; delta->changed_mask[c] = 1;
        } else if (b_empty && a_empty) {
            delta->transition_class[c] = TRM_TRANSITION_UNCHANGED_EMPTY;
            unch_empty++;
        } else if (b_correct && a_correct && fixed_mask[c]) {
            delta->transition_class[c] = TRM_TRANSITION_UNCHANGED_FIXED_CORRECT;
            unch_correct++;
        } else if (b_correct && a_correct) {
            delta->transition_class[c] = TRM_TRANSITION_UNCHANGED_WRITABLE_CORRECT;
            unch_correct++;
        } else if (b_wrong && a_wrong && b == a) {
            delta->transition_class[c] = TRM_TRANSITION_UNCHANGED_WRITABLE_WRONG;
            unch_wrong++;
        } else {
            delta->transition_class[c] = TRM_TRANSITION_UNCHANGED_EMPTY;
            unch_empty++;
        }

        if (delta->changed_mask[c]) changed_count++;
    }

    delta->changed_cell_count = changed_count;
    delta->correct_addition_count = correct_add;
    delta->wrong_addition_count = wrong_add;
    delta->correction_count = corr;
    delta->regression_count = regr;
    delta->wrong_to_different_wrong_count = wrong_diff;
    delta->unchanged_correct_count = unch_correct;
    delta->unchanged_wrong_count = unch_wrong;
    delta->unchanged_empty_count = unch_empty;

    int32_t total_add_corr = (int32_t)correct_add + (int32_t)corr;
    delta->net_correct_gain = total_add_corr - (int32_t)regr;
    delta->wrong_cell_delta = (int32_t)delta->wrong_addition_count - (int32_t)delta->correction_count;

    return 0;
}

int elpis_trm_structural_delta_validate(
    const elpis_semantic_trm_structural_delta_v1 *delta) {
    if (delta->abi_version != TRM_STRUCTURAL_DELTA_VERSION) return -1;
    return 0;
}

int elpis_write_trm_structural_delta(const char *path,
    const elpis_semantic_trm_structural_delta_v1 *d) {
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    size_t sz = sizeof(*d);
    if (fwrite(d, 1, sz, f) != sz) { fclose(f); return -1; }
    fclose(f);
    return 0;
}

int elpis_read_trm_structural_delta(const char *path,
    elpis_semantic_trm_structural_delta_v1 *out) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    size_t sz = sizeof(*out);
    if (fread(out, 1, sz, f) != sz) { fclose(f); return -1; }
    fclose(f);
    return elpis_trm_structural_delta_validate(out);
}
