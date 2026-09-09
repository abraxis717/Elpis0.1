/* test_embedding_boundary.c - hermetic non-dependency and runtime boundary tests. */
#define _DEFAULT_SOURCE
#include "elpis/sha256.h"
#include "elpis_semantic/embedding_collection.h"
#include "elpis_semantic/embedding_coverage.h"
#include "elpis_semantic/embedding_metric.h"
#include "elpis_semantic/embedding_neighborhood.h"
#include "elpis_semantic/embedding_profile.h"
#include "elpis_semantic/embedding_ref.h"
#include "elpis_semantic/embedding_storage.h"
#include "elpis_semantic/embedding_vector.h"
#include "elpis_semantic/embedding_view.h"
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

static const char *root_dir = ELPIS_SEMANTIC_SOURCE_ROOT;
static const char *hacf_root = ELPIS_HACF_SOURCE_ROOT;

/* Expected bytes are bound to manifests/Elpis2.1.9.RELEASE_MANIFEST.json. */
static const char *p0_hashes[] = {
    "a2ffd9f383198fbacc000b5b1254b556bdd46adc1b40e3e1e5611234eff33691",
    "973b1c50c8dedf9451642426b13ccf55678cafa7a60fb368925810e3ca3af0f1",
    "6d34777f944ae40e063d32c373829abfaeeca48a1b307a3eb9163494e9dbcc7a",
    "4298e507b69d7dc2b214f6dbcdcac5606e3ab44e459e8dc28acd02772d7b1ac0",
    "cbe17281bf830cc52572dce5da1cd8547ab2007ffa0dfa01f3232e5203f15e7f",
    "b372beaec8b3f3729da918273b1adc931de3c7f1bcc61905b94bcbd4d617b13e",
    "3a2a63164af4095f44e4443265498fa324ebbf37a182eee246681649de656046",
    "6b122b3d6612ffebd6d0d9075504015729dd3df667169222f003acf6e6e8ea7c"
};
static const char *p0_headers[] = {
    "include/elpis_semantic/identity.h",
    "include/elpis_semantic/hypergraph.h",
    "include/elpis_semantic/type_registry.h",
    "include/elpis_semantic/snapshot.h",
    "include/elpis_semantic/segment.h",
    "include/elpis_semantic/query_overlay.h",
    "include/elpis_semantic/snapshot_view.h",
    "include/elpis_semantic/hacf_mapping.h"
};
static const char *p0_names[] = {
    "identity.h",
    "hypergraph.h",
    "type_registry.h",
    "snapshot.h",
    "segment.h",
    "query_overlay.h",
    "snapshot_view.h",
    "hacf_mapping.h"
};

static int file_sha256(const char *path, char out[65]) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    unsigned char buf[8192];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), f)) != 0) {
        elpis_sha256_update(&ctx, buf, n);
    }
    if (ferror(f)) { fclose(f); return -1; }
    fclose(f);
    uint8_t digest[32];
    elpis_sha256_final(&ctx, digest);
    static const char hex[] = "0123456789abcdef";
    for (size_t i = 0; i < sizeof(digest); ++i) {
        out[i * 2] = hex[digest[i] >> 4];
        out[i * 2 + 1] = hex[digest[i] & 0x0f];
    }
    out[64] = '\0';
    return 0;
}

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

static int group_clean(const char *const *relpaths, const char *const *needles,
                       const char *label) {
    for (size_t i = 0; relpaths[i]; ++i) {
        char full[2048];
        if (snprintf(full, sizeof(full), "%s/%s", root_dir, relpaths[i]) >= (int)sizeof(full)) {
            fprintf(stderr, "FAIL: path overflow for %s\n", relpaths[i]);
            return 0;
        }
        int rc = file_contains_any(full, needles);
        if (rc < 0) {
            fprintf(stderr, "FAIL: cannot inspect %s\n", relpaths[i]);
            return 0;
        }
        if (rc > 0) {
            fprintf(stderr, "FAIL: %s boundary token in %s\n", label, relpaths[i]);
            return 0;
        }
    }
    return 1;
}

int main(void) {
    int passed = 0, failed = 0;
    char fullpath[2048];

    for (size_t i = 0; i < sizeof(p0_headers) / sizeof(p0_headers[0]); ++i) {
        if (snprintf(fullpath, sizeof(fullpath), "%s/%s", root_dir, p0_headers[i]) >= (int)sizeof(fullpath)) {
            fprintf(stderr, "FAIL: path overflow for %s\n", p0_names[i]); failed++; continue;
        }
        char hash[65];
        if (file_sha256(fullpath, hash) != 0) {
            fprintf(stderr, "FAIL: cannot compute %s hash\n", p0_names[i]); failed++;
        } else if (strcmp(hash, p0_hashes[i]) != 0) {
            fprintf(stderr, "FAIL: %s differs from sealed Elpis2.1.9 manifest\n", p0_names[i]); failed++;
        } else passed++;
    }

    if (snprintf(fullpath, sizeof(fullpath), "%s/include/elpis/cascade.h", hacf_root) >= (int)sizeof(fullpath)) {
        failed++;
    } else if (access(fullpath, F_OK) == 0) passed++;
    else { fprintf(stderr, "FAIL: HACF cascade.h not found\n"); failed++; }

    static const char *embedding_srcs[] = {
        "src/embedding/embedding_profile.c",
        "src/embedding/embedding_vector.c",
        "src/embedding/embedding_ref.c",
        "src/embedding/embedding_collection.c",
        "src/embedding/embedding_metric.c",
        "src/embedding/embedding_neighborhood.c",
        "src/embedding/embedding_writer.c",
        "src/embedding/embedding_view.c",
        "src/embedding/embedding_coverage.c",
        "src/embedding/embedding_reader.c",
        NULL
    };

    static const char *machine_paths[] = {
        "$ELPIS_" "CANON_ROOT", "$HOME", "/home/", "/Users/", "/srv/elpis-private-fixture/", NULL
    };
    static const char *model_exec[] = {"cudaMalloc", "cudnn", "nccl", NULL};
    static const char *network[] = {"libcurl", "curl_", "socket(", "connect(", "TCP", NULL};
    static const char *relations[] = {
        "SUPPORTS", "CONTRADICTS", "CAUSES", "REQUIRES", "SAME_AS",
        "EQUIVALENT_TO", "SEMANTICALLY_NEAR", NULL
    };
    static const char *lexical[] = {"BM25", "TF-IDF", "inverted_index", NULL};
    static const char *admission[] = {"RUNTIME_ADMIT", "runtime_admission", "admission(", NULL};
    static const char *grid81[] = {"Grid81", "grid81", NULL};
    static const char *trm[] = {"TinyRecursive", "TRM_", "trm_", NULL};
    static const char *r3[] = {"hacf_r3", "R3_", "r3_", NULL};
    static const char *deficit[] = {"CONTEXT_SUFFICIENT", "CONTEXT_DEFICIT", "RETRIEVAL_REQUIRED", NULL};

    const struct {
        const char *label;
        const char *const *needles;
    } checks[] = {
        {"machine-path", machine_paths},
        {"model-execution", model_exec},
        {"network", network},
        {"semantic-relation", relations},
        {"lexical-retrieval", lexical},
        {"runtime-admission", admission},
        {"Grid81", grid81},
        {"TRM", trm},
        {"R3", r3},
        {"context-deficit", deficit},
    };

    for (size_t i = 0; i < sizeof(checks) / sizeof(checks[0]); ++i) {
        if (group_clean(embedding_srcs, checks[i].needles, checks[i].label)) passed++;
        else failed++;
    }

    /* The public embedding header set is included by this translation unit.
       Reaching runtime is therefore a compile witness, not a bare assertion. */
    passed++;

    printf("Boundary tests: %d passed, %d failed\n", passed, failed);
    return failed ? 1 : 0;
}
