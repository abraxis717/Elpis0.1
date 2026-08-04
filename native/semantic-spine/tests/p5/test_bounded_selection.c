/* test_bounded_selection.c — P5 deterministic selection tests */
#include "elpis_semantic/bounded_view_candidate.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>

static void set_digest(hacf_digest *d, uint32_t seed) {
    memset(d, 0, HACF_DIGEST_BYTES);
    d->bytes[0] = (uint8_t)(seed & 0xFF);
}

static int test_mandatory_before_optional(void) {
    bounded_view_candidate_record a, b;
    memset(&a, 0, sizeof(a));
    memset(&b, 0, sizeof(b));
    set_digest(&a.object_digest, 0xBB);
    set_digest(&b.object_digest, 0xAA);
    a.candidate_priority_class = CANDIDATE_PRIORITY_MANDATORY;
    b.candidate_priority_class = CANDIDATE_PRIORITY_OPTIONAL;
    if (elpis_bounded_view_candidate_cmp(&a, &b) >= 0) {
        printf("FAIL: mandatory not before optional\n"); return 1;
    }
    printf("PASS: mandatory_before_optional\n");
    return 0;
}

static int test_requirement_level_ordering(void) {
    bounded_view_candidate_record a, b;
    memset(&a, 0, sizeof(a));
    memset(&b, 0, sizeof(b));
    set_digest(&a.object_digest, 0xBB);
    set_digest(&b.object_digest, 0xAA);
    a.candidate_priority_class = b.candidate_priority_class = CANDIDATE_PRIORITY_MANDATORY;
    a.requirement_level = PREFERRED;
    b.requirement_level = MANDATORY;
    if (elpis_bounded_view_candidate_cmp(&a, &b) < 0) {
        printf("FAIL: mandatory should come before preferred\n"); return 1;
    }
    printf("PASS: requirement_level_ordering\n");
    return 0;
}

static int test_higher_authority_first(void) {
    bounded_view_candidate_record a, b;
    memset(&a, 0, sizeof(a));
    memset(&b, 0, sizeof(b));
    set_digest(&a.object_digest, 0xBB);
    set_digest(&b.object_digest, 0xAA);
    a.candidate_priority_class = b.candidate_priority_class = CANDIDATE_PRIORITY_SEMANTIC;
    a.requirement_level = b.requirement_level = PREFERRED;
    a.origin_kind = b.origin_kind = CANDIDATE_ORIGIN_SEMANTIC_GRAPH_NEIGHBOR;
    a.graph_hop = b.graph_hop = 1;
    a.effective_authority = 100;
    b.effective_authority = 50;
    if (elpis_bounded_view_candidate_cmp(&a, &b) >= 0) {
        printf("FAIL: higher authority should come first\n"); return 1;
    }
    printf("PASS: higher_authority_first\n");
    return 0;
}

static int test_digest_tiebreak(void) {
    bounded_view_candidate_record a, b;
    memset(&a, 0, sizeof(a));
    memset(&b, 0, sizeof(b));
    set_digest(&a.object_digest, 0xBB);
    set_digest(&b.object_digest, 0xAA);
    a.candidate_priority_class = b.candidate_priority_class = CANDIDATE_PRIORITY_SEMANTIC;
    a.requirement_level = b.requirement_level = PREFERRED;
    a.origin_kind = b.origin_kind = CANDIDATE_ORIGIN_SEMANTIC_GRAPH_NEIGHBOR;
    a.graph_hop = b.graph_hop = 1;
    a.effective_authority = b.effective_authority = 50;
    a.distinct_provenance_count = b.distinct_provenance_count = 1;
    int cmp = elpis_bounded_view_candidate_cmp(&a, &b);
    if (cmp < 0) {
        printf("FAIL: digest tiebreak wrong (BB after AA)\n"); return 1;
    }
    printf("PASS: digest_tiebreak\n");
    return 0;
}

static int test_ranking_deterministic(void) {
    elpis_semantic_bounded_view_candidate_set_v1 set1, set2;
    elpis_bounded_view_candidate_set_init(&set1);
    elpis_bounded_view_candidate_set_init(&set2);
    elpis_bounded_view_rank_candidates(&set1);
    elpis_bounded_view_rank_candidates(&set2);
    hacf_digest d1, d2;
    elpis_bounded_view_candidate_set_identity(&set1, &d1);
    elpis_bounded_view_candidate_set_identity(&set2, &d2);
    if (memcmp(&d1, &d2, HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: ranking not deterministic\n"); return 1;
    }
    printf("PASS: ranking_deterministic\n");
    return 0;
}

int main(void) {
    int f = 0;
    f += test_mandatory_before_optional();
    f += test_requirement_level_ordering();
    f += test_higher_authority_first();
    f += test_digest_tiebreak();
    f += test_ranking_deterministic();
    if (f == 0) printf("ALL test_bounded_selection TESTS PASSED\n");
    else printf("FAILURES: %d\n", f);
    return f;
}
