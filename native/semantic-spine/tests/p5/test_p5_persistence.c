/* test_p5_persistence.c — P5 persistence round-trip tests */
#include "elpis_semantic/context_iteration_policy.h"
#include "elpis_semantic/identity.h"
#include "elpis_semantic/bounded_view_policy.h"
#include "elpis_semantic/context_rebind.h"
#include "elpis_semantic/context_iteration_state.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>

static void set_digest(hacf_digest *d, uint32_t seed) {
    memset(d, 0, HACF_DIGEST_BYTES);
    d->bytes[0] = (uint8_t)(seed & 0xFF);
}

static int test_iteration_policy_round_trip(void) {
    elpis_semantic_context_iteration_policy_v1 policy;
    elpis_context_iteration_policy_default(&policy);
    const char *path = "/tmp/p5_test_policy.bin";
    remove(path);
    int rc = elpis_write_iteration_policy(path, &policy);
    if (rc != SEMANTIC_OK) { printf("FAIL: write: %d\n", rc); return 1; }
    elpis_semantic_context_iteration_policy_v1 read_policy;
    rc = elpis_read_iteration_policy(path, &read_policy);
    if (rc != SEMANTIC_OK) { printf("FAIL: read: %d\n", rc); return 1; }
    if (memcmp(&policy.policy_identity, &read_policy.policy_identity,
               HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: identity mismatch\n"); return 1;
    }
    remove(path);
    printf("PASS: iteration_policy_round_trip\n");
    return 0;
}

static int test_bounded_view_policy_round_trip(void) {
    elpis_semantic_bounded_view_policy_v1 policy;
    elpis_bounded_view_policy_default(&policy);
    const char *path = "/tmp/p5_test_bvp.bin";
    int rc = elpis_write_bounded_view_policy(path, &policy);
    if (rc != SEMANTIC_OK) { printf("FAIL: write: %d\n", rc); return 1; }
    elpis_semantic_bounded_view_policy_v1 read_policy;
    rc = elpis_read_bounded_view_policy(path, &read_policy);
    if (rc != SEMANTIC_OK) { printf("FAIL: read: %d\n", rc); return 1; }
    if (memcmp(&policy.policy_identity, &read_policy.policy_identity,
               HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: identity mismatch\n"); return 1;
    }
    remove(path);
    printf("PASS: bounded_view_policy_round_trip\n");
    return 0;
}

static int test_truncation_rejected(void) {
    elpis_semantic_bounded_view_policy_v1 policy;
    elpis_bounded_view_policy_default(&policy);
    const char *path = "/tmp/p5_test_trunc.bin";
    FILE *f = fopen(path, "wb");
    if (f) { fwrite(&policy, 1, sizeof(policy) - 10, f); fclose(f); }
    elpis_semantic_bounded_view_policy_v1 read_policy;
    int rc = elpis_read_bounded_view_policy(path, &read_policy);
    if (rc == SEMANTIC_OK) { printf("FAIL: truncation not rejected\n"); return 1; }
    remove(path);
    printf("PASS: truncation_rejected\n");
    return 0;
}

static int test_trailing_bytes_rejected(void) {
    elpis_semantic_bounded_view_policy_v1 policy;
    elpis_bounded_view_policy_default(&policy);
    const char *path = "/tmp/p5_test_trail.bin";
    FILE *f = fopen(path, "wb");
    if (f) {
        fwrite(&policy, 1, sizeof(policy), f);
        uint8_t extra[10];
        memset(extra, 0xFF, 10);
        fwrite(extra, 1, 10, f);
        fclose(f);
    }
    elpis_semantic_bounded_view_policy_v1 read_policy;
    int rc = elpis_read_bounded_view_policy(path, &read_policy);
    if (rc == SEMANTIC_OK) { printf("FAIL: trailing bytes not rejected\n"); return 1; }
    remove(path);
    printf("PASS: trailing_bytes_rejected\n");
    return 0;
}

static int test_field_width_corruption_rejected(void) {
    elpis_semantic_bounded_view_policy_v1 policy;
    elpis_bounded_view_policy_default(&policy);
    const char *path = "/tmp/p5_test_corrupt.bin";
    elpis_write_bounded_view_policy(path, &policy);
    FILE *f = fopen(path, "r+b");
    if (f) {
        fseek(f, 0, SEEK_SET);
        uint32_t bad = 0;
        fwrite(&bad, 1, 4, f);
        fclose(f);
    }
    elpis_semantic_bounded_view_policy_v1 read_policy;
    int rc = elpis_read_bounded_view_policy(path, &read_policy);
    if (rc == SEMANTIC_OK) { printf("FAIL: corruption not rejected\n"); return 1; }
    remove(path);
    printf("PASS: field_width_corruption_rejected\n");
    return 0;
}

static int test_preexisting_destination_preserved(void) {
    const char *path = "/tmp/p5_test_existing.bin";
    FILE *f = fopen(path, "wb");
    if (f) {
        uint8_t sentinel[32];
        memset(sentinel, 0xAB, 32);
        fwrite(sentinel, 1, 32, f);
        fclose(f);
    }
    elpis_semantic_bounded_view_policy_v1 policy;
    elpis_bounded_view_policy_default(&policy);
    elpis_write_bounded_view_policy(path, &policy);
    remove(path);
    printf("PASS: preexisting_destination_preserved\n");
    return 0;
}

static int test_endianness_equality(void) {
    /* Writer/reader use fixed-width BE encoding — endianness must match */
    elpis_semantic_context_iteration_policy_v1 policy;
    elpis_context_iteration_policy_default(&policy);
    const char *path = "/tmp/p5_test_endian.bin";
    remove(path);
    int rc = elpis_write_iteration_policy(path, &policy);
    if (rc != SEMANTIC_OK) { printf("FAIL: endianness write: %d\n", rc); return 1; }
    elpis_semantic_context_iteration_policy_v1 read_policy;
    rc = elpis_read_iteration_policy(path, &read_policy);
    if (rc != SEMANTIC_OK) { printf("FAIL: endianness read: %d\n", rc); return 1; }
    if (memcmp(&policy.policy_identity, &read_policy.policy_identity,
               HACF_DIGEST_BYTES) != 0) {
        printf("FAIL: endianness identity mismatch\n"); return 1;
    }
    remove(path);
    printf("PASS: endianness_equality\n");
    return 0;
}

int main(void) {
    int f = 0;
    f += test_iteration_policy_round_trip();
    f += test_bounded_view_policy_round_trip();
    f += test_truncation_rejected();
    f += test_trailing_bytes_rejected();
    f += test_field_width_corruption_rejected();
    f += test_preexisting_destination_preserved();
    f += test_endianness_equality();
    if (f == 0) printf("ALL test_p5_persistence TESTS PASSED\n");
    else printf("FAILURES: %d\n", f);
    return f;
}
