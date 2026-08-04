/* test_evidence_span.c — Evidence span tests. */
#include "elpis_semantic/evidence_span.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stdio.h>



#include <string.h>

/* Helper: compare a digest against all-zero */
static const uint8_t ZERO_DIGEST[32] = {0};
static int digest_is_zero(const hacf_digest *d) {
    return memcmp(d->bytes, ZERO_DIGEST, 32) == 0;
}
#include <stdlib.h>

static int tests_run = 0;
static int tests_pass = 0;

#define TEST(name, expr) do { \
    tests_run++; \
    if (expr) { tests_pass++; } \
    else { fprintf(stderr, "FAIL: %s at %s:%d\n", #expr, __FILE__, __LINE__); } \
} while(0)

static void test_span_init(void) {
    elpis_evidence_span_v1 span;
    elpis_evidence_span_init(&span);
    TEST(init_abi, span.abi_version == EVIDENCE_SPAN_ABI_VERSION);
    TEST(init_reserved, memcmp(span.reserved, (const uint8_t[48]){0}, sizeof(span.reserved)) == 0);
}

static void test_span_exact_byte_span_accepted(void) {
    const char *text = "Hello, world! This is test text.";
    elpis_evidence_span_v1 span;
    elpis_evidence_span_init(&span);

    memset(span.retrieval_expansion_digest.bytes, 1, 32);
    memset(span.retrieval_bundle_digest.bytes, 1, 32);
    memset(span.retrieval_item_attachment_digest.bytes, 1, 32);
    memset(span.evidence_node_digest.bytes, 1, 32);

    span.byte_start = 0;
    span.byte_end_exclusive = 13; /* "Hello, world!" */

    /* Compute span digest */
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, (const uint8_t *)text, 13);
    elpis_sha256_final(&ctx, span.span_bytes_digest.bytes);

    TEST(exact_span_valid, elpis_evidence_span_validate(&span, (const uint8_t *)text, strlen(text)) == SEMANTIC_OK);
}

static void test_span_byte_start_equal_to_end_rejected(void) {
    elpis_evidence_span_v1 span;
    elpis_evidence_span_init(&span);
    memset(span.retrieval_expansion_digest.bytes, 1, 32);
    memset(span.retrieval_bundle_digest.bytes, 1, 32);
    memset(span.retrieval_item_attachment_digest.bytes, 1, 32);
    memset(span.evidence_node_digest.bytes, 1, 32);
    span.byte_start = 5;
    span.byte_end_exclusive = 5;

    TEST(empty_span_rejected, elpis_evidence_span_validate(&span, NULL, 0) != SEMANTIC_OK);
}

static void test_span_end_beyond_text_rejected(void) {
    const char *text = "short";
    elpis_evidence_span_v1 span;
    elpis_evidence_span_init(&span);
    memset(span.retrieval_expansion_digest.bytes, 1, 32);
    memset(span.retrieval_bundle_digest.bytes, 1, 32);
    memset(span.retrieval_item_attachment_digest.bytes, 1, 32);
    memset(span.evidence_node_digest.bytes, 1, 32);
    span.byte_start = 0;
    span.byte_end_exclusive = 100;

    TEST(end_beyond_text_rejected, elpis_evidence_span_validate(&span, (const uint8_t *)text, 5) != SEMANTIC_OK);
}

static void test_span_digest_mismatch_rejected(void) {
    const char *text = "Hello, world! This is test text.";
    elpis_evidence_span_v1 span;
    elpis_evidence_span_init(&span);
    memset(span.retrieval_expansion_digest.bytes, 1, 32);
    memset(span.retrieval_bundle_digest.bytes, 1, 32);
    memset(span.retrieval_item_attachment_digest.bytes, 1, 32);
    memset(span.evidence_node_digest.bytes, 1, 32);
    span.byte_start = 0;
    span.byte_end_exclusive = 5;
    memset(span.span_bytes_digest.bytes, 0xFF, 32); /* wrong digest */

    TEST(digest_mismatch_rejected, elpis_evidence_span_validate(&span, (const uint8_t *)text, strlen(text)) != SEMANTIC_OK);
}

static void test_span_identity_deterministic(void) {
    elpis_evidence_span_v1 a, b;
    elpis_evidence_span_init(&a);
    elpis_evidence_span_init(&b);

    memset(a.retrieval_expansion_digest.bytes, 1, 32);
    memset(b.retrieval_expansion_digest.bytes, 1, 32);
    memset(a.retrieval_bundle_digest.bytes, 1, 32);
    memset(b.retrieval_bundle_digest.bytes, 1, 32);
    memset(a.retrieval_item_attachment_digest.bytes, 1, 32);
    memset(b.retrieval_item_attachment_digest.bytes, 1, 32);
    memset(a.evidence_node_digest.bytes, 1, 32);
    memset(b.evidence_node_digest.bytes, 1, 32);
    a.byte_start = 0; b.byte_start = 0;
    a.byte_end_exclusive = 5; b.byte_end_exclusive = 5;
    memcpy(a.span_bytes_digest.bytes, b.span_bytes_digest.bytes, 32);

    hacf_digest id_a, id_b;
    elpis_evidence_span_identity(&a, &id_a);
    elpis_evidence_span_identity(&b, &id_b);
    TEST(identity_deterministic, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) == 0);
}

static void test_span_utf8_multibyte_as_bytes(void) {
    /* UTF-8 multibyte: "café" = 5 bytes (c,a,f,\xc3\xa9) */
    const uint8_t text[] = {0x63, 0x61, 0x66, 0xC3, 0xA9, 0x20}; /* "café " = 6 bytes */
    elpis_evidence_span_v1 span;
    elpis_evidence_span_init(&span);
    memset(span.retrieval_expansion_digest.bytes, 1, 32);
    memset(span.retrieval_bundle_digest.bytes, 1, 32);
    memset(span.retrieval_item_attachment_digest.bytes, 1, 32);
    memset(span.evidence_node_digest.bytes, 1, 32);

    /* Span the multibyte char: byte 3-5 = 0xC3 0xA9 */
    span.byte_start = 3;
    span.byte_end_exclusive = 5;

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, text + 3, 2);
    elpis_sha256_final(&ctx, span.span_bytes_digest.bytes);

    TEST(utf8_multibyte_as_bytes, elpis_evidence_span_validate(&span, text, 6) == SEMANTIC_OK);
}

static void test_span_whitespace_preserved(void) {
    const char *text = "  hello  ";
    elpis_evidence_span_v1 span;
    elpis_evidence_span_init(&span);
    memset(span.retrieval_expansion_digest.bytes, 1, 32);
    memset(span.retrieval_bundle_digest.bytes, 1, 32);
    memset(span.retrieval_item_attachment_digest.bytes, 1, 32);
    memset(span.evidence_node_digest.bytes, 1, 32);
    span.byte_start = 0;
    span.byte_end_exclusive = strlen(text);

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, (const uint8_t *)text, strlen(text));
    elpis_sha256_final(&ctx, span.span_bytes_digest.bytes);

    TEST(whitespace_preserved, elpis_evidence_span_validate(&span, (const uint8_t *)text, strlen(text)) == SEMANTIC_OK);
}

static void test_span_same_bytes_different_offset(void) {
    const char *text = "abab";
    elpis_evidence_span_v1 a, b;
    elpis_evidence_span_init(&a);
    elpis_evidence_span_init(&b);

    memset(a.retrieval_expansion_digest.bytes, 1, 32);
    memset(b.retrieval_expansion_digest.bytes, 1, 32);
    memset(a.retrieval_bundle_digest.bytes, 1, 32);
    memset(b.retrieval_bundle_digest.bytes, 1, 32);
    memset(a.retrieval_item_attachment_digest.bytes, 1, 32);
    memset(b.retrieval_item_attachment_digest.bytes, 1, 32);
    memset(a.evidence_node_digest.bytes, 1, 32);
    memset(b.evidence_node_digest.bytes, 1, 32);

    a.byte_start = 0; a.byte_end_exclusive = 2; /* "ab" at 0 */
    b.byte_start = 2; b.byte_end_exclusive = 4; /* "ab" at 2 */

    /* Same span bytes digest */
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx, (const uint8_t *)"ab", 2);
    hacf_digest sd;
    elpis_sha256_final(&ctx, sd.bytes);
    memcpy(a.span_bytes_digest.bytes, sd.bytes, 32);
    memcpy(b.span_bytes_digest.bytes, sd.bytes, 32);

    hacf_digest id_a, id_b;
    elpis_evidence_span_identity(&a, &id_a);
    elpis_evidence_span_identity(&b, &id_b);
    TEST(same_bytes_different_offset_distinct, memcmp(id_a.bytes, id_b.bytes, HACF_DIGEST_BYTES) != 0);
}

int main(void) {
    test_span_init();
    test_span_exact_byte_span_accepted();
    test_span_byte_start_equal_to_end_rejected();
    test_span_end_beyond_text_rejected();
    test_span_digest_mismatch_rejected();
    test_span_identity_deterministic();
    test_span_utf8_multibyte_as_bytes();
    test_span_whitespace_preserved();
    test_span_same_bytes_different_offset();

    printf("evidence_span: %d/%d tests passed\n", tests_pass, tests_run);
    return (tests_pass == tests_run) ? 0 : 1;
}
