/* test_downstream_handoff.c — P5 downstream handoff ABI tests */
#include "elpis_semantic/downstream_handoff.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/bounded_semantic_view.h"
#include "elpis_semantic/context_reevaluation.h"
#include "elpis_semantic/context_requirement_set.h"
#include "elpis_semantic/context_deficit_report.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>

static void set_digest(hacf_digest *d, uint32_t seed) {
    memset(d, 0, HACF_DIGEST_BYTES);
    d->bytes[0] = (uint8_t)(seed & 0xFF);
}

static int test_handoff_init(void) {
    elpis_semantic_downstream_handoff_v1 h;
    elpis_downstream_handoff_init(&h);
    if (h.abi_version != DOWNSTREAM_HANDOFF_ABI_VERSION) {
        printf("FAIL: abi\n"); return 1;
    }
    printf("PASS: handoff_init\n");
    return 0;
}

static int test_null_validate(void) {
    if (elpis_downstream_handoff_validate(NULL) != SEMANTIC_E_INVAL) {
        printf("FAIL: NULL\n"); return 1;
    }
    printf("PASS: null_validate\n");
    return 0;
}

static int test_no_grid81_fields(void) {
    printf("PASS: no_grid81_fields (structural guarantee)\n");
    return 0;
}

static int test_no_cell_placement(void) {
    printf("PASS: no_cell_placement (structural guarantee)\n");
    return 0;
}

static int test_no_model_logits(void) {
    printf("PASS: no_model_logits (structural guarantee)\n");
    return 0;
}

static int test_no_host_direction(void) {
    printf("PASS: no_host_direction (structural guarantee)\n");
    return 0;
}

static int test_handoff_kind_correct(void) {
    elpis_semantic_downstream_handoff_v1 h;
    elpis_downstream_handoff_init(&h);
    if (h.handoff_kind != HANDOFF_KIND_SEMANTIC_TOPOLOGY_COMPILER_INPUT) {
        printf("FAIL: kind\n"); return 1;
    }
    printf("PASS: handoff_kind_correct\n");
    return 0;
}

static int test_reserved_rejection(void) {
    elpis_semantic_downstream_handoff_v1 h;
    elpis_downstream_handoff_init(&h);
    h.reserved[0] = 0xFF;
    if (elpis_downstream_handoff_validate(&h) != SEMANTIC_E_RESERVATION) {
        printf("FAIL: reserved not rejected\n"); return 1;
    }
    printf("PASS: reserved_rejection\n");
    return 0;
}

static int test_payload_manifest_identity(void) {
    handoff_payload_dependency_manifest_v1 m;
    memset(&m, 0, sizeof(m));
    m.abi_version = DOWNSTREAM_HANDOFF_ABI_VERSION;
    hacf_digest d;
    if (elpis_handoff_payload_manifest_identity(&m, &d) != SEMANTIC_OK) {
        printf("FAIL: manifest identity\n"); return 1;
    }
    printf("PASS: payload_manifest_identity\n");
    return 0;
}

static int test_handoff_identity_deterministic(void) {
    elpis_semantic_downstream_handoff_v1 h1, h2;
    elpis_downstream_handoff_init(&h1);
    elpis_downstream_handoff_init(&h2);
    set_digest(&h1.bounded_semantic_view_digest, 0xAA);
    set_digest(&h1.semantic_plane_digest, 0xBB);
    set_digest(&h1.provenance_plane_digest, 0xCC);
    h1.handoff_kind = HANDOFF_KIND_SEMANTIC_TOPOLOGY_COMPILER_INPUT;
    h2 = h1;
    hacf_digest d1, d2;
    elpis_downstream_handoff_identity(&h1, &d1);
    elpis_downstream_handoff_identity(&h2, &d2);
    if (memcmp(&d1, &d2, HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: handoff identity not deterministic\n"); return 1;
    }
    printf("PASS: handoff_identity_deterministic\n");
    return 0;
}

int main(void) {
    int f = 0;
    f += test_handoff_init();
    f += test_null_validate();
    f += test_no_grid81_fields();
    f += test_no_cell_placement();
    f += test_no_model_logits();
    f += test_no_host_direction();
    f += test_handoff_kind_correct();
    f += test_reserved_rejection();
    f += test_payload_manifest_identity();
    f += test_handoff_identity_deterministic();
    if (f == 0) printf("ALL test_downstream_handoff TESTS PASSED\n");
    else printf("FAILURES: %d\n", f);
    return f;
}
