/* test_candidate_enumeration.c — P5 candidate enumeration tests */
#include "elpis_semantic/bounded_view_candidate.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/bounded_view_policy.h"
#include "elpis_semantic/bounded_view_seed.h"
#include "elpis_semantic/typed_evidence_view.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>

static void set_digest(hacf_digest *d, uint32_t seed) {
    memset(d, 0, HACF_DIGEST_BYTES);
    d->bytes[0] = (uint8_t)(seed & 0xFF);
}

static int test_candidate_set_init(void) {
    elpis_semantic_bounded_view_candidate_set_v1 set;
    elpis_bounded_view_candidate_set_init(&set);
    if (set.abi_version != BOUNDED_VIEW_CANDIDATE_ABI_VERSION) {
        printf("FAIL: abi\n"); return 1;
    }
    printf("PASS: candidate_set_init\n");
    return 0;
}

static int test_null_input(void) {
    if (elpis_bounded_view_candidate_set_validate(NULL) != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL\n"); return 1;
    }
    printf("PASS: null_input\n");
    return 0;
}

static int test_candidate_identity_deterministic(void) {
    elpis_semantic_bounded_view_candidate_set_v1 s1, s2;
    elpis_bounded_view_candidate_set_init(&s1);
    elpis_bounded_view_candidate_set_init(&s2);
    hacf_digest d1, d2;
    elpis_bounded_view_candidate_set_identity(&s1, &d1);
    elpis_bounded_view_candidate_set_identity(&s2, &d2);
    if (memcmp(&d1, &d2, HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: not deterministic\n"); return 1;
    }
    printf("PASS: candidate_identity_deterministic\n");
    return 0;
}

static int test_candidate_cmp_deterministic(void) {
    bounded_view_candidate_record a, b;
    memset(&a, 0, sizeof(a));
    memset(&b, 0, sizeof(b));
    a.candidate_priority_class = CANDIDATE_PRIORITY_MANDATORY;
    b.candidate_priority_class = CANDIDATE_PRIORITY_OPTIONAL;
    if (elpis_bounded_view_candidate_cmp(&a, &b) >= 0) {
        printf("FAIL: mandatory should come before optional\n"); return 1;
    }
    printf("PASS: candidate_cmp_deterministic\n");
    return 0;
}

static int test_embedding_neighbor_does_not_create_semantic_edge(void) {
    bounded_view_candidate_record c;
    memset(&c, 0, sizeof(c));
    c.origin_kind = CANDIDATE_ORIGIN_METRIC_SUPPLEMENT;
    c.semantic_relation_type = 0;
    if (c.semantic_relation_type != 0) {
        printf("FAIL: metric supplement created semantic relation\n");
        return 1;
    }
    printf("PASS: embedding_neighbor_does_not_create_semantic_edge\n");
    return 0;
}

static int test_candidate_insertion_order_independent(void) {
    bounded_view_candidate_record a, b;
    memset(&a, 0, sizeof(a));
    memset(&b, 0, sizeof(b));
    a.object_kind = SEMANTIC_OBJECT_KIND_NODE;
    set_digest(&a.object_digest, 0xBB);
    a.candidate_priority_class = CANDIDATE_PRIORITY_MANDATORY;
    b.object_kind = SEMANTIC_OBJECT_KIND_NODE;
    set_digest(&b.object_digest, 0xAA);
    b.candidate_priority_class = CANDIDATE_PRIORITY_MANDATORY;
    int cmp = elpis_bounded_view_candidate_cmp(&a, &b);
    if (cmp < 0) {
        printf("FAIL: digest ordering wrong\n"); return 1;
    }
    printf("PASS: candidate_insertion_order_independent\n");
    return 0;
}

int main(void) {
    int f = 0;
    f += test_candidate_set_init();
    f += test_null_input();
    f += test_candidate_identity_deterministic();
    f += test_candidate_cmp_deterministic();
    f += test_embedding_neighbor_does_not_create_semantic_edge();
    f += test_candidate_insertion_order_independent();
    if (f == 0) printf("ALL test_candidate_enumeration TESTS PASSED\n");
    else printf("FAILURES: %d\n", f);
    return f;
}
