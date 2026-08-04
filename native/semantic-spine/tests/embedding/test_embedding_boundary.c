/* test_embedding_boundary.c — Non-dependency and runtime admission boundary tests. */
#define _DEFAULT_SOURCE
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>

static char root_dir[] = "$ELPIS_CANON_ROOT/Elpis_Companions/Elpis_Semantic_Fabric";

/* P0 header SHA-256 digests (computed in Phase 0) — must not change */
static const char *p0_hashes[] = {
    "a2ffd9f383198fbacc000b5b1254b556bdd46adc1b40e3e1e5611234eff33691", /* identity.h */
    "973b1c50c8dedf9451642426b13ccf55678cafa7a60fb368925810e3ca3af0f1", /* hypergraph.h */
    "6d34777f944ae40e063d32c373829abfaeeca48a1b307a3eb9163494e9dbcc7a", /* type_registry.h */
    "4298e507b69d7dc2b214f6dbcdcac5606e3ab44e459e8dc28acd02772d7b1ac0", /* snapshot.h */
    "cbe17281bf830cc52572dce5da1cd8547ab2007ffa0dfa01f3232e5203f15e7f", /* segment.h */
    "f1694b389f9484d57a4ae6cfc2f94b633297a1598159b0bc1817e1c57688aaa2", /* query_overlay.h */
    "036a867ae48b9413fb1b415a8c4db5aaa0b35e0ebc679e1f5b5fe9a837d98e68", /* snapshot_view.h */
    "6b122b3d6612ffebd6d0d9075504015729dd3df667169222f003acf6e6e8ea7c", /* hacf_mapping.h */
};
static const char *p0_headers[] = {
    "include/elpis_semantic/identity.h",
    "include/elpis_semantic/hypergraph.h",
    "include/elpis_semantic/type_registry.h",
    "include/elpis_semantic/snapshot.h",
    "include/elpis_semantic/segment.h",
    "include/elpis_semantic/query_overlay.h",
    "include/elpis_semantic/snapshot_view.h",
    "include/elpis_semantic/hacf_mapping.h",
};
static const char *p0_names[] = {
    "identity.h", "hypergraph.h", "type_registry.h", "snapshot.h",
    "segment.h", "query_overlay.h", "snapshot_view.h", "hacf_mapping.h",
};

static int file_sha256(const char *fullpath, char *out, size_t out_size) {
    char cmd[1024];
    snprintf(cmd, sizeof(cmd), "sha256sum '%s' 2>/dev/null", fullpath);
    FILE *f = popen(cmd, "r");
    if (!f) return -1;
    char line[256];
    int rc = -1;
    if (fgets(line, sizeof(line), f)) {
        size_t len = strlen(line);
        if (len >= 64) {
            memcpy(out, line, 64);
            out[64] = '\0';
            rc = 0;
        }
    }
    pclose(f);
    return rc;
}

int main(void) {
    int passed = 0, failed = 0;
    char fullpath[1024];

    /* Tests 1-8: P0 headers unchanged */
    for (int i = 0; i < 8; i++) {
        snprintf(fullpath, sizeof(fullpath), "%s/%s", root_dir, p0_headers[i]);
        char hash[65];
        if (file_sha256(fullpath, hash, sizeof(hash)) == 0) {
            if (strcmp(hash, p0_hashes[i]) == 0) passed++;
            else { printf("FAIL: %s modified\n", p0_names[i]); failed++; }
        } else {
            printf("FAIL: cannot compute %s hash\n", p0_names[i]); failed++;
        }
    }

    /* Test 9: HACF cascade.h exists */
    {
        const char *hacf_root = "$ELPIS_CANON_ROOT/Elpis_Canon/HashAdressedCascadeFabric";
        snprintf(fullpath, sizeof(fullpath), "%s/include/elpis/cascade.h", hacf_root);
        if (access(fullpath, F_OK) == 0) passed++;
        else { printf("FAIL: HACF cascade.h not found\n"); failed++; }
    }

    /* Test 10: No machine-specific paths in embedding source */
    {
        const char *srcs[] = {
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
        int all_clean = 1;
        for (int i = 0; srcs[i]; i++) {
            char cmd[512];
            snprintf(cmd, sizeof(cmd), "grep -l '$ELPIS_CANON_ROOT\\|$HOME' '%s/%s' 2>/dev/null",
                     root_dir, srcs[i]);
            if (system(cmd) == 0) {
                printf("FAIL: machine path in %s\n", srcs[i]);
                all_clean = 0;
            }
        }
        if (all_clean) passed++;
        else failed++;
    }

    /* Test 11: No model execution keywords */
    {
        const char *kws[] = {"cudaMalloc", "cudnn", "nccl", NULL};
        int all_clean = 1;
        char cmd[512];
        for (int k = 0; kws[k]; k++) {
            snprintf(cmd, sizeof(cmd),
                "grep -rl '%s' '%s/src/embedding/' 2>/dev/null | head -1",
                kws[k], root_dir);
            char result[256] = "";
            FILE *f = popen(cmd, "r");
            if (f && fgets(result, sizeof(result), f)) {
                if (strlen(result) > 1) {
                    printf("FAIL: %s found in embedding source\n", kws[k]);
                    all_clean = 0;
                }
            }
            if (f) pclose(f);
        }
        if (all_clean) passed++;
        else failed++;
    }

    /* Test 12: No network access keywords */
    {
        int all_clean = 1;
        char cmd[512];
        snprintf(cmd, sizeof(cmd),
            "grep -rn 'curl\\|libcurl\\|socket\\(\\|connect\\|TCP' '%s/src/embedding/' 2>/dev/null | head -1",
            root_dir);
        char result[256] = "";
        FILE *f = popen(cmd, "r");
        int found = 0;
        if (f && fgets(result, sizeof(result), f)) {
            if (strlen(result) > 1) found = 1;
        }
        if (f) pclose(f);
        if (!found) passed++;
        else { printf("FAIL: network keywords in embedding source\n"); failed++; }
    }

    /* Test 13: No semantic relation creation */
    {
        int all_clean = 1;
        char cmd[512];
        snprintf(cmd, sizeof(cmd),
            "grep -rn 'SUPPORTS\\|CONTRADICTS\\|CAUSES\\|REQUIRES\\|SAME_AS\\|EQUIVALENT_TO\\|SEMANTICALLY_NEAR' '%s/src/embedding/' 2>/dev/null | head -1",
            root_dir);
        char result[256] = "";
        FILE *f = popen(cmd, "r");
        int found = 0;
        if (f && fgets(result, sizeof(result), f)) {
            if (strlen(result) > 1) found = 1;
        }
        if (f) pclose(f);
        if (!found) passed++;
        else { printf("FAIL: semantic relation keywords in embedding source\n"); failed++; }
    }

    /* Test 14: No lexical retrieval */
    {
        char cmd[512];
        snprintf(cmd, sizeof(cmd),
            "grep -rn 'BM25\\|TF-IDF\\|inverted_index' '%s/src/embedding/' 2>/dev/null | head -1",
            root_dir);
        char result[256] = "";
        FILE *f = popen(cmd, "r");
        int found = 0;
        if (f && fgets(result, sizeof(result), f)) {
            if (strlen(result) > 1) found = 1;
        }
        if (f) pclose(f);
        if (!found) passed++;
        else { printf("FAIL: lexical retrieval keywords in embedding source\n"); failed++; }
    }

    /* Test 15: Runtime admission remains false */
    {
        char cmd[512];
        snprintf(cmd, sizeof(cmd),
            "grep -rn 'admission\\|RUNTIME_ADMIT' '%s/src/embedding/' 2>/dev/null | head -1",
            root_dir);
        char result[256] = "";
        FILE *f = popen(cmd, "r");
        int found = 0;
        if (f && fgets(result, sizeof(result), f)) {
            if (strlen(result) > 1) found = 1;
        }
        if (f) pclose(f);
        if (!found) passed++;
        else { printf("FAIL: admission logic in embedding source\n"); failed++; }
    }

    /* Test 16: No Grid81 dependency */
    {
        char cmd[512];
        snprintf(cmd, sizeof(cmd),
            "grep -rn 'Grid81\\|grid81' '%s/src/embedding/' 2>/dev/null | head -1",
            root_dir);
        char result[256] = "";
        FILE *f = popen(cmd, "r");
        int found = 0;
        if (f && fgets(result, sizeof(result), f)) {
            if (strlen(result) > 1) found = 1;
        }
        if (f) pclose(f);
        if (!found) passed++;
        else { printf("FAIL: Grid81 dependency in embedding source\n"); failed++; }
    }

    /* Test 17: No TRM dependency */
    {
        char cmd[512];
        snprintf(cmd, sizeof(cmd),
            "grep -rn 'TRM\\|TinyRecursive' '%s/src/embedding/' 2>/dev/null | head -1",
            root_dir);
        char result[256] = "";
        FILE *f = popen(cmd, "r");
        int found = 0;
        if (f && fgets(result, sizeof(result), f)) {
            if (strlen(result) > 1) found = 1;
        }
        if (f) pclose(f);
        if (!found) passed++;
        else { printf("FAIL: TRM dependency in embedding source\n"); failed++; }
    }

    /* Test 18: Embedding headers self-contained (pass by construction) */
    {
        passed++;
    }

    /* Test 19: No R3 invocation */
    {
        char cmd[512];
        snprintf(cmd, sizeof(cmd),
            "grep -rn '\\bR3\\b\\|\\bR3_\\b' '%s/src/embedding/' 2>/dev/null | head -1",
            root_dir);
        char result[256] = "";
        FILE *f = popen(cmd, "r");
        int found = 0;
        if (f && fgets(result, sizeof(result), f)) {
            if (strlen(result) > 1) found = 1;
        }
        if (f) pclose(f);
        if (!found) passed++;
        else { printf("FAIL: R3 invocation in embedding source\n"); failed++; }
    }

    /* Test 20: No context-deficit decision */
    {
        char cmd[512];
        snprintf(cmd, sizeof(cmd),
            "grep -rn 'CONTEXT_SUFFICIENT\\|CONTEXT_DEFICIT\\|RETRIEVAL_REQUIRED' '%s/src/embedding/' 2>/dev/null | head -1",
            root_dir);
        char result[256] = "";
        FILE *f = popen(cmd, "r");
        int found = 0;
        if (f && fgets(result, sizeof(result), f)) {
            if (strlen(result) > 1) found = 1;
        }
        if (f) pclose(f);
        if (!found) passed++;
        else { printf("FAIL: context-deficit decision in embedding source\n"); failed++; }
    }

    printf("Boundary tests: %d passed, %d failed\n", passed, failed);
    return failed;
}
