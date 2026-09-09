/* test_context_boundaries.c - hermetic P2 boundary enforcement. */
#include "elpis_semantic/context_deficit_report.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#ifndef ELPIS_SEMANTIC_SOURCE_ROOT
#error "ELPIS_SEMANTIC_SOURCE_ROOT must be supplied by CMake"
#endif
#ifndef ELPIS_HACF_SOURCE_ROOT
#error "ELPIS_HACF_SOURCE_ROOT must be supplied by CMake"
#endif

static int passed = 0, failed = 0;
#define ASSERT_EQ(a, b) do { \
    if ((a) == (b)) passed++; \
    else { failed++; fprintf(stderr, "FAIL %s:%d %s != %s\n", __FILE__, __LINE__, #a, #b); } \
} while(0)
#define ASSERT_TRUE(cond) do { \
    if (cond) passed++; \
    else { failed++; fprintf(stderr, "FAIL %s:%d %s is false\n", __FILE__, __LINE__, #cond); } \
} while(0)

static const char *p2_sources[] = {
    "src/context/context_requirement.c",
    "src/context/context_requirement_set.c",
    "src/context/context_deficit_policy.c",
    "src/context/context_deficit.c",
    "src/context/context_deficit_report.c",
    "src/context/retrieval_requirement.c",
    "src/context/retrieval_requirement_bundle.c",
    "src/context/context_writer.c",
    "src/context/context_reader.c",
    NULL
};

static int file_contains_any(const char *path, const char *const *needles) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return -1; }
    long end = ftell(f);
    if (end < 0 || end > 16L * 1024L * 1024L) { fclose(f); return -1; }
    if (fseek(f, 0, SEEK_SET) != 0) { fclose(f); return -1; }
    size_t size = (size_t)end;
    char *buf = malloc(size + 1u);
    if (!buf) { fclose(f); return -1; }
    if (size && fread(buf, 1, size, f) != size) { free(buf); fclose(f); return -1; }
    fclose(f);
    buf[size] = '\0';
    int found = 0;
    for (size_t i = 0; needles[i]; ++i) {
        if (strstr(buf, needles[i]) != NULL) { found = 1; break; }
    }
    free(buf);
    return found;
}

static int sources_clean(const char *const *needles, const char *label) {
    for (size_t i = 0; p2_sources[i]; ++i) {
        char full[2048];
        if (snprintf(full, sizeof(full), "%s/%s", ELPIS_SEMANTIC_SOURCE_ROOT, p2_sources[i]) >= (int)sizeof(full)) {
            fprintf(stderr, "FAIL: path overflow for %s\n", p2_sources[i]);
            return 0;
        }
        int rc = file_contains_any(full, needles);
        if (rc < 0) {
            fprintf(stderr, "FAIL: cannot inspect %s\n", p2_sources[i]);
            return 0;
        }
        if (rc > 0) {
            fprintf(stderr, "FAIL: %s boundary token in %s\n", label, p2_sources[i]);
            return 0;
        }
    }
    return 1;
}

int main(void) {
    const char *p2_headers[] = {
        "include/elpis_semantic/context_requirement.h",
        "include/elpis_semantic/context_requirement_set.h",
        "include/elpis_semantic/context_deficit_policy.h",
        "include/elpis_semantic/context_deficit.h",
        "include/elpis_semantic/context_deficit_report.h",
        "include/elpis_semantic/retrieval_requirement.h",
        "include/elpis_semantic/retrieval_requirement_bundle.h",
        NULL
    };

    for (size_t i = 0; p2_sources[i]; ++i) {
        char path[2048];
        struct stat st;
        ASSERT_TRUE(snprintf(path, sizeof(path), "%s/%s", ELPIS_SEMANTIC_SOURCE_ROOT, p2_sources[i]) < (int)sizeof(path));
        ASSERT_EQ(stat(path, &st), 0);
    }
    for (size_t i = 0; p2_headers[i]; ++i) {
        char path[2048];
        struct stat st;
        ASSERT_TRUE(snprintf(path, sizeof(path), "%s/%s", ELPIS_SEMANTIC_SOURCE_ROOT, p2_headers[i]) < (int)sizeof(path));
        ASSERT_EQ(stat(path, &st), 0);
    }

    static const char *gpu[] = {
        "#include <cuda", "#include \"cuda", "cudaMalloc", "cudnn", "nccl", NULL
    };
    static const char *network[] = {
        "#include <sys/socket.h>", "#include <netinet/", "socket(", "connect(",
        "send(", "recv(", "libcurl", "curl_", NULL
    };
    static const char *r3[] = {"hacf_r3", "R3_", "r3_", NULL};
    static const char *trm[] = {"TinyRecursive", "TRM_", "trm_", NULL};
    static const char *grid81[] = {"Grid81", "grid81", NULL};
    static const char *admission[] = {"RUNTIME_ADMIT", "runtime_admission", "admission(", NULL};

    ASSERT_TRUE(sources_clean(gpu, "GPU"));
    ASSERT_TRUE(sources_clean(network, "network"));
    ASSERT_TRUE(sources_clean(r3, "R3"));

    {
        char path[2048];
        struct stat st;
        ASSERT_TRUE(snprintf(path, sizeof(path), "%s/include/elpis/cascade.h",
                             ELPIS_HACF_SOURCE_ROOT) < (int)sizeof(path));
        ASSERT_EQ(stat(path, &st), 0);
    }

    ASSERT_TRUE(sources_clean(trm, "TRM"));
    ASSERT_TRUE(sources_clean(grid81, "Grid81"));
    ASSERT_TRUE(sources_clean(admission, "runtime-admission"));

    {
        elpis_semantic_requirement_result_v1 dummy_result;
        elpis_semantic_context_requirement_set_v1 dummy_set;
        elpis_semantic_context_deficit_policy_v1 dummy_policy;
        memset(&dummy_result, 0, sizeof(dummy_result));
        memset(&dummy_set, 0, sizeof(dummy_set));
        memset(&dummy_policy, 0, sizeof(dummy_policy));
        uint32_t disposition = DISP_CONTEXT_SUFFICIENT;
        ASSERT_EQ(elpis_context_deficit_report_disposition(
            &dummy_result, 0, &dummy_set, NULL, 0,
            &dummy_policy, &disposition), SEMANTIC_OK);
        ASSERT_EQ(disposition, DISP_EVALUATION_BLOCKED);
    }

    printf("Context boundary tests: %d passed, %d failed\n", passed, failed);
    return failed ? 1 : 0;
}
