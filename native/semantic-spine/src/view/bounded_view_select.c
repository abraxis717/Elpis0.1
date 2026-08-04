/* bounded_view_select.c — Deterministic candidate ranking for P5. */
#include "elpis_semantic/bounded_view_candidate.h"
#include "elpis_semantic/identity.h"
#include <unistd.h>
#include <stdio.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <arpa/inet.h>
#include "elpis/sha256.h"
#include <string.h>
#include <stdint.h>

/* Simple atomic write — declared in p5_writer.c */
extern int p5_simple_write(const char *path, const uint8_t *data, size_t sz);

static void write_domain_tag(elpis_sha256_ctx *ctx, const char *domain) {
    size_t len = strlen(domain);
    uint32_t be_len = htonl((uint32_t)len);
    elpis_sha256_update(ctx, &be_len, 4);
    elpis_sha256_update(ctx, domain, len);
}

static void write_u32_be(elpis_sha256_ctx *ctx, uint32_t val) {
    uint32_t be = htonl(val);
    elpis_sha256_update(ctx, &be, 4);
}





/* Sort candidate set in-place using lexicographic priority tuple.
 * Must be deterministic — no randomness, no timestamps. */
int elpis_bounded_view_rank_candidates(
    elpis_semantic_bounded_view_candidate_set_v1 *candidate_set) {
    if (!candidate_set) return SEMANTIC_E_INVAL;

    uint32_t n = candidate_set->candidate_count;
    if (n <= 1) return SEMANTIC_OK;

    /* Deterministic insertion sort (stable) */
    for (uint32_t i = 1; i < n; i++) {
        bounded_view_candidate_record key = candidate_set->ordered_candidates[i];
        uint32_t j = i;
        while (j > 0 && elpis_bounded_view_candidate_cmp(
                   &key, &candidate_set->ordered_candidates[j - 1]) < 0) {
            candidate_set->ordered_candidates[j] =
                candidate_set->ordered_candidates[j - 1];
            j--;
        }
        candidate_set->ordered_candidates[j] = key;
    }

    /* Recompute set identity after sort */
    elpis_bounded_view_candidate_set_identity(
        candidate_set, &candidate_set->candidate_set_digest);
    return SEMANTIC_OK;
}

int elpis_bounded_view_compute_candidate_record_digest(
    const bounded_view_candidate_record *rec, hacf_digest *out) {
    return elpis_bounded_view_candidate_record_digest(rec, out);
}
