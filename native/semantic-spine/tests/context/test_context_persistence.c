/* test_context_persistence.c — Storage round-trip for P2 objects. */
#define _POSIX_C_SOURCE 200809L
#include "elpis_semantic/context_writer.h"
#include "elpis_semantic/context_reader.h"
#include "elpis_semantic/context_requirement_set.h"
#include "elpis_semantic/context_deficit_policy.h"
#include "elpis_semantic/identity.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>

static int passed = 0, failed = 0;
#define ASSERT_OK(expr) do { int r = (expr); if (r == SEMANTIC_OK) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s\n", __FILE__, __LINE__, #expr); } } while(0)
#define ASSERT_NEQ(expr, v) do { int r = (expr); if (r == (v)) { failed++; fprintf(stderr, "FAIL %s:%d %s == %d\n", __FILE__, __LINE__, #expr, v); } else passed++; } while(0)
#define ASSERT_EQ(a, b) do { if ((a) == (b)) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d %s != %s\n", __FILE__, __LINE__, #a, #b); } } while(0)
#define ASSERT_DIGEST_EQ(a, b) do { if (memcmp((a)->bytes, (b)->bytes, HACF_DIGEST_BYTES) == 0) passed++; else { failed++; fprintf(stderr, "FAIL %s:%d digests differ\n", __FILE__, __LINE__); } } while(0)

#define TEST_DIR "/tmp/p2_persistence_test"
#define SETUP_DIR() do { mkdir(TEST_DIR, 0755); } while(0)

int main(void) {
    SETUP_DIR();

    /* Create a requirement set for round-trip test */
    elpis_semantic_context_requirement_set_v1 original_set;
    elpis_context_requirement_set_init(&original_set);
    hacf_digest req_d1, req_d2;
    memset(&req_d1, 0x11, sizeof(req_d1));
    memset(&req_d2, 0x22, sizeof(req_d2));
    elpis_context_requirement_set_add(&original_set, &req_d1);
    elpis_context_requirement_set_add(&original_set, &req_d2);
    hacf_digest overlay, composed;
    memset(&overlay, 0xAA, sizeof(overlay));
    memset(&composed, 0xBB, sizeof(composed));
    memcpy(original_set.target_query_overlay_digest.bytes, overlay.bytes, HACF_DIGEST_BYTES);
    memcpy(original_set.target_composed_view_digest.bytes, composed.bytes, HACF_DIGEST_BYTES);
    /* Compute identity AND store it into the struct so the writer persists it */
    hacf_digest original_set_id;
    elpis_context_requirement_set_identity(&original_set, &original_set_id);
    memcpy(original_set.requirement_set_identity.bytes, original_set_id.bytes, HACF_DIGEST_BYTES);

    /* Test: requirement-set round trip */
    {
        char path[512];
        snprintf(path, sizeof(path), "%s/reqset.dat", TEST_DIR);
        /* Write */
        ASSERT_OK(elpis_write_requirement_set(path, &original_set));
        /* Read back */
        elpis_semantic_context_requirement_set_v1 read_set;
        ASSERT_OK(elpis_read_requirement_set(path, &read_set));
        /* Verify identity matches */
        ASSERT_DIGEST_EQ(&original_set_id, &read_set.requirement_set_identity);
        ASSERT_EQ(read_set.requirement_count, original_set.requirement_count);
        unlink(path);
    }

    /* Test: policy round trip */
    {
        char path[512];
        snprintf(path, sizeof(path), "%s/policy.dat", TEST_DIR);
        elpis_semantic_context_deficit_policy_v1 original_policy;
        elpis_context_deficit_policy_init(&original_policy);
        original_policy.mandatory_failure_behavior = MAND_BEHAVIOR_RETRIEVAL_REQUIRED;
        original_policy.preferred_failure_behavior = PREFERRED_BEHAVIOR_REPORT_ONLY;
        original_policy.diagnostic_failure_behavior = DIAG_BEHAVIOR_REPORT_ONLY;
        original_policy.max_retrieval_requirements = 128;
        original_policy.max_deficits = 256;
        original_policy.deficit_priority_policy = PRIORITY_LEVEL_THEN_TYPE;
        original_policy.retrieval_dedup_policy = DEDUP_EXACT_COLLAPSE;
        original_policy.unsupported_requirement_behavior = UNSUPPORTED_BEHAVIOR_FAIL_CLOSED;
        hacf_digest policy_id;
        elpis_context_deficit_policy_identity(&original_policy, &policy_id);
        /* Store identity into struct so writer persists it */
        memcpy(original_policy.policy_identity.bytes, policy_id.bytes, HACF_DIGEST_BYTES);
        /* Write */
        ASSERT_OK(elpis_write_deficit_policy(path, &original_policy));
        /* Read back */
        elpis_semantic_context_deficit_policy_v1 read_policy;
        memset(&read_policy, 0, sizeof(read_policy));
        int pread = elpis_read_deficit_policy(path, &read_policy);
        fprintf(stderr, "DEBUG: read_deficit_policy returned %d\n", pread);
        fprintf(stderr, "DEBUG: abi_version=%u, mandatory=%u, preferred=%u, diagnostic=%u, max_rr=%u, max_d=%u, priority=%u, dedup=%u, unsupported=%u\n",
                read_policy.abi_version, read_policy.mandatory_failure_behavior,
                read_policy.preferred_failure_behavior, read_policy.diagnostic_failure_behavior,
                read_policy.max_retrieval_requirements, read_policy.max_deficits,
                read_policy.deficit_priority_policy, read_policy.retrieval_dedup_policy,
                read_policy.unsupported_requirement_behavior);
        fprintf(stderr, "DEBUG: reserved[0..3]=%u %u %u %u\n",
                read_policy.reserved[0], read_policy.reserved[1],
                read_policy.reserved[2], read_policy.reserved[3]);
        ASSERT_OK(pread);
        ASSERT_DIGEST_EQ(&policy_id, &read_policy.policy_identity);
        unlink(path);
    }

    /* Test: atomic no-replace publication */
    {
        char path[512];
        snprintf(path, sizeof(path), "%s/noreplace.dat", TEST_DIR);
        /* First write */
        ASSERT_OK(elpis_write_requirement_set(path, &original_set));
        /* Second write should fail (pre-existing) */
        ASSERT_NEQ(elpis_write_requirement_set(path, &original_set), SEMANTIC_OK);
        unlink(path);
    }

    /* Test: truncated file rejection */
    {
        char path[512];
        snprintf(path, sizeof(path), "%s/truncated.dat", TEST_DIR);
        FILE *fp = fopen(path, "wb");
        /* Write partial magic only */
        uint32_t magic = 0x52515300;
        fwrite(&magic, 4, 1, fp);
        fclose(fp);
        elpis_semantic_context_requirement_set_v1 read_set;
        ASSERT_NEQ(elpis_read_requirement_set(path, &read_set), SEMANTIC_OK);
        unlink(path);
    }

    /* Test: corrupt digest rejection */
    {
        char path[512];
        snprintf(path, sizeof(path), "%s/corrupt.dat", TEST_DIR);
        /* Write valid then tamper */
        ASSERT_OK(elpis_write_requirement_set(path, &original_set));
        /* Read file, corrupt one byte in payload */
        FILE *fp = fopen(path, "r+b");
        if (fp) {
            struct stat st;
            fstat(fileno(fp), &st);
            /* Corrupt byte near end (before hash) */
            fseek(fp, st.st_size - 33, SEEK_SET);
            unsigned char bad = 0xFF;
            fwrite(&bad, 1, 1, fp);
            fclose(fp);
        }
        elpis_semantic_context_requirement_set_v1 read_set;
        ASSERT_NEQ(elpis_read_requirement_set(path, &read_set), SEMANTIC_OK);
        unlink(path);
    }

    rmdir(TEST_DIR);
    printf("Context persistence tests: %d passed, %d failed\n", passed, failed);
    return failed > 0 ? 1 : 0;
}
