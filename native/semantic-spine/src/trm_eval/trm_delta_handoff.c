/* trm_delta_handoff.c — P10 structural-delta handoff. */
#include "elpis_semantic/trm_delta_handoff.h"
#include <stdio.h>
#include <string.h>
#include "elpis/sha256.h"

void elpis_trm_delta_handoff_init(elpis_semantic_trm_delta_handoff_v1 *h) {
    memset(h, 0, sizeof(*h));
    h->abi_version = TRM_DELTA_HANDOFF_VERSION;
    h->handoff_kind = TRM_HANDOFF_GUARDED_TRM_STRUCTURAL_DELTA_EVIDENCE;
    h->benchmark_is_sudoku_structural = 1;
    h->no_semantic_correctness_claim = 1;
    h->categorical_deltas_preserve_from_to = 1;
    h->digit_subtraction_no_meaning = 1;
    h->candidate_admitted_committed_distinct = 1;
    h->projector_requires_separate_qualification = 1;
    h->no_residual81_definition = 1;
    h->no_host_direction = 1;
    h->runtime_admission_false = 1;
}

int elpis_trm_delta_handoff_identity(
    const elpis_semantic_trm_delta_handoff_v1 *h, hacf_digest *out) {
    uint8_t hash[32];
    elpis_sha256((const void *)h, offsetof(elpis_semantic_trm_delta_handoff_v1, reserved), hash);
    memcpy(out->bytes, hash, sizeof(out->bytes));
    return 0;
}

int elpis_trm_delta_handoff_validate(const elpis_semantic_trm_delta_handoff_v1 *h) {
    if (h->abi_version != TRM_DELTA_HANDOFF_VERSION) return -1;
    return 0;
}

int elpis_write_trm_delta_handoff(const char *path,
    const elpis_semantic_trm_delta_handoff_v1 *h) {
    FILE *f = fopen(path, "wb"); if (!f) return -1;
    size_t sz = sizeof(*h);
    if (fwrite(h, 1, sz, f) != sz) { fclose(f); return -1; }
    fclose(f); return 0;
}

int elpis_read_trm_delta_handoff(const char *path,
    elpis_semantic_trm_delta_handoff_v1 *out) {
    FILE *f = fopen(path, "rb"); if (!f) return -1;
    size_t sz = sizeof(*out);
    if (fread(out, 1, sz, f) != sz) { fclose(f); return -1; }
    fclose(f); return elpis_trm_delta_handoff_validate(out);
}
