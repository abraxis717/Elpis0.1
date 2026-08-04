/* python_r1_wrapper.c — thin C wrapper for R1 qualification workflow.
 *
 * Build:
 *   gcc -shared -fPIC -o libr1_hacf_wrapper.so python_r1_wrapper.c \
 *       -I../include \
 *       -Wl,--whole-archive libelpis_hybrid.a libelpis_vector.a \
 *       libelpis_embedding.a libelpis_corpus.a libelpis_chunking.a \
 *       libelpis_hash.a libelpis_fms.a libelpis_cascade.a libelpis_graph.a \
 *       -Wl,--no-whole-archive -lsqlite3 -lpthread -lm -lstdc++
 */

#include "elpis/chunking.h"
#include "elpis/corpus.h"
#include "elpis/embedding_provider.h"
#include "elpis/fms.h"
#include "elpis/fms_pal_posix.h"
#include "elpis/hybrid_retrieval.h"
#include "elpis/vector_index.h"
#include "elpis/vector_shard.h"
#include "elpis/sha256.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

typedef struct {
    char label[64];
    char chunk[65];
    char doc[65];
    char ns[96];
    char auth[32];
} cr_t;

typedef struct r1_env {
    elpis_corpus       *corpus;
    elpis_embedder     *embedder;
    fms_ctx            *fms;
    elpis_vector_index *index;
    elpis_embedding_profile profile;

    char corpus_digest[65];
    char shard_digest[65];
    char corpus_manifest_json[65536];
    size_t corpus_manifest_json_len;
    char vindex_manifest_json[65536];
    size_t vindex_manifest_json_len;

    cr_t refs[64];
    size_t n_refs;

    void *shard_bytes;
    size_t shard_len;
} r1_env_t;

static void mkdirp(const char *p) {
    char tmp[1024];
    snprintf(tmp, sizeof tmp, "%s", p);
    for (char *c = tmp + 1; *c; c++) {
        if (*c == '/') {
            *c = '\0'; mkdir(tmp, 0755); *c = '/';
        }
    }
    mkdir(tmp, 0755);
}

r1_env_t *r1_env_create(const char *state_root,
                         const char **labels, const char **texts,
                         const char **namespaces, const char **authorities,
                         int n_docs, char error_buf[256]) {
    r1_env_t *env = calloc(1, sizeof(r1_env_t));
    if (!env) { snprintf(error_buf, 256, "calloc"); return NULL; }

    char corpus_dir[512];
    snprintf(corpus_dir, sizeof corpus_dir, "%s/corpus", state_root);
    mkdirp(corpus_dir);
    if (elpis_corpus_open(corpus_dir, &env->corpus) != 0) {
        snprintf(error_buf, 256, "corpus_open failed"); free(env); return NULL;
    }

    for (int i = 0; i < n_docs; i++) {
        elpis_ingest_meta m;
        memset(&m, 0, sizeof m);
        m.ns = namespaces[i]; m.authority = authorities[i];
        m.media_type = ELPIS_MT_TEXT; m.origin = labels[i];
        elpis_ingest_result ir;
        memset(&ir, 0, sizeof ir);
        if (elpis_corpus_ingest_bytes(env->corpus, texts[i], strlen(texts[i]), &m, &ir) != 0) {
            snprintf(error_buf, 256, "ingest failed for %s", labels[i]);
            elpis_corpus_close(env->corpus); free(env); return NULL;
        }
        if (env->n_refs < 64) {
            strncpy(env->refs[env->n_refs].label, labels[i], 63);
            memcpy(env->refs[env->n_refs].doc, ir.doc_digest, 64);
            env->refs[env->n_refs].doc[64] = '\0';
            env->refs[env->n_refs].ns[0] = '\0';
            env->refs[env->n_refs].auth[0] = '\0';
            env->refs[env->n_refs].chunk[0] = '\0';
            env->n_refs++;
        }
    }

    {
        char *cj = NULL;
        if (elpis_corpus_manifest_json(env->corpus, &cj, env->corpus_digest) == 0 && cj) {
            size_t len = strlen(cj);
            env->corpus_manifest_json_len = len < 65535 ? len : 65535;
            memcpy(env->corpus_manifest_json, cj, env->corpus_manifest_json_len);
            env->corpus_manifest_json[env->corpus_manifest_json_len] = '\0';
            elpis_free(cj);
        }
    }

    {
        elpis_chunk_ref refs[128];
        uint32_t n = 0;
        elpis_corpus_list_chunks(env->corpus, NULL, NULL, 0, 128, refs, &n);
        for (uint32_t ci = 0; ci < n; ci++) {
            for (size_t li = 0; li < env->n_refs; li++) {
                if (strcmp(env->refs[li].doc, refs[ci].doc_digest) == 0) {
                    memcpy(env->refs[li].chunk, refs[ci].chunk_digest, 64);
                    env->refs[li].chunk[64] = '\0';
                    strncpy(env->refs[li].ns, refs[ci].ns, 95);
                    strncpy(env->refs[li].auth, refs[ci].authority, 31);
                }
            }
        }
    }

    if (elpis_embedder_fixture_create(ELPIS_NORM_L2, &env->embedder) != 0) {
        snprintf(error_buf, 256, "embedder_create failed");
        elpis_corpus_close(env->corpus); free(env); return NULL;
    }
    elpis_embedder_profile(env->embedder, &env->profile);

    elpis_vshard_input inputs[128];
    memset(inputs, 0, sizeof inputs);
    int n_inputs = 0;
    for (size_t i = 0; i < env->n_refs; i++) {
        char *text = NULL;
        if (elpis_corpus_chunk_text(env->corpus, env->refs[i].chunk, &text) != 0)
            continue;
        float vec[ELPIS_EMBEDDING_DIM];
        elpis_embedder_embed(env->embedder, text, strlen(text), vec, ELPIS_EMBEDDING_DIM);
        elpis_free(text);

        strncpy(inputs[n_inputs].chunk_digest, env->refs[i].chunk, 64);
        strncpy(inputs[n_inputs].doc_digest, env->refs[i].doc, 64);
        inputs[n_inputs].ns = env->refs[i].ns;
        inputs[n_inputs].authority = env->refs[i].auth;
        float *v = malloc(ELPIS_EMBEDDING_DIM * sizeof(float));
        memcpy(v, vec, ELPIS_EMBEDDING_DIM * sizeof(float));
        inputs[n_inputs].vector = v;
        n_inputs++;
    }

    {
        char sd[65];
        if (elpis_vshard_build(inputs, n_inputs, &env->profile, env->corpus_digest,
                               &env->shard_bytes, &env->shard_len, sd) != 0) {
            snprintf(error_buf, 256, "vshard_build failed");
            for (int i = 0; i < n_inputs; i++) free((void*)inputs[i].vector);
            elpis_embedder_destroy(env->embedder);
            elpis_corpus_close(env->corpus); free(env); return NULL;
        }
        memcpy(env->shard_digest, sd, 64);
        env->shard_digest[64] = '\0';
    }
    for (int i = 0; i < n_inputs; i++) free((void*)inputs[i].vector);

    {
        char cold_root[512];
        snprintf(cold_root, sizeof cold_root, "%s/cold", state_root);
        mkdirp(cold_root);
        fms_pal *pal = fms_pal_posix_create(cold_root);
        if (!pal) {
            snprintf(error_buf, 256, "fms_pal failed");
            elpis_free(env->shard_bytes);
            elpis_embedder_destroy(env->embedder);
            elpis_corpus_close(env->corpus); free(env); return NULL;
        }
        fms_config cfg;
        memset(&cfg, 0, sizeof cfg);
        cfg.tier_budget[FMS_WARM] = 16ull << 20;
        cfg.tier_budget[FMS_COLD] = 512ull << 20;
        cfg.domain_ceiling[FMS_DOM_RAM] = 16ull << 20;
        cfg.domain_ceiling[FMS_DOM_STORAGE] = 512ull << 20;
        cfg.high_wm = 0.90f; cfg.low_wm = 0.70f;
        cfg.max_objects = 64;
        cfg.hot_absent_policy = FMS_REJECT;
        cfg.cold_absent_policy = FMS_FOLD_DOWN;
        env->fms = fms_create(&cfg, pal);
        if (!env->fms) {
            snprintf(error_buf, 256, "fms_create failed");
            elpis_free(env->shard_bytes);
            elpis_embedder_destroy(env->embedder);
            elpis_corpus_close(env->corpus); free(env); return NULL;
        }
    }

    if (elpis_vector_index_create(env->fms, &env->profile, env->corpus_digest, &env->index) != ELPIS_VEC_OK) {
        snprintf(error_buf, 256, "vindex_create failed");
        fms_destroy(env->fms);
        elpis_free(env->shard_bytes);
        elpis_embedder_destroy(env->embedder);
        elpis_corpus_close(env->corpus); free(env); return NULL;
    }
    if (elpis_vector_index_add_shard_bytes(env->index, env->shard_bytes, env->shard_len, NULL) != ELPIS_VEC_OK) {
        snprintf(error_buf, 256, "add_shard failed: %s", elpis_vector_index_error(env->index));
        elpis_vector_index_destroy(env->index);
        fms_destroy(env->fms);
        elpis_free(env->shard_bytes);
        elpis_embedder_destroy(env->embedder);
        elpis_corpus_close(env->corpus); free(env); return NULL;
    }
    elpis_free(env->shard_bytes); env->shard_bytes = NULL; env->shard_len = 0;

    {
        char *vj = NULL;
        char vj_digest[65];
        if (elpis_vector_index_manifest_json(env->index, &vj, vj_digest) == 0 && vj) {
            size_t len = strlen(vj);
            env->vindex_manifest_json_len = len < 65535 ? len : 65535;
            memcpy(env->vindex_manifest_json, vj, env->vindex_manifest_json_len);
            env->vindex_manifest_json[env->vindex_manifest_json_len] = '\0';
            elpis_free(vj);
        }
    }

    snprintf(error_buf, 256, "ok");
    return env;
}

void r1_env_destroy(r1_env_t *env) {
    if (!env) return;
    if (env->index) elpis_vector_index_destroy(env->index);
    if (env->fms) fms_destroy(env->fms);
    if (env->embedder) elpis_embedder_destroy(env->embedder);
    if (env->corpus) elpis_corpus_close(env->corpus);
    if (env->shard_bytes) elpis_free(env->shard_bytes);
    free(env);
}

int r1_env_embed(r1_env_t *env, const char *text, int text_len, float *out, int out_dim) {
    if (!env || !env->embedder || !out) return -1;
    return elpis_embedder_embed(env->embedder, text, text_len, out, out_dim);
}

int r1_env_retrieve(r1_env_t *env,
                    const char *query_text,
                    const float *query_vector, int query_dim,
                    uint32_t lexical_limit, uint32_t dense_limit,
                    uint32_t primary_limit, uint32_t total_limit,
                    char *bundle_json_out, int bundle_json_cap,
                    char *bundle_digest_out,
                    char *query_digest_out,
                    char *corpus_manifest_digest_out,
                    char *vindex_manifest_digest_out,
                    char *fusion_policy_digest_out,
                    int *item_count_out,
                    char error_buf[256]) {
    if (!env || !env->corpus || !env->index) {
        snprintf(error_buf, 256, "env not ready"); return -1;
    }

    elpis_hybrid_policy policy;
    elpis_hybrid_policy_default(&policy);
    policy.lexical_limit = lexical_limit;
    policy.dense_limit = dense_limit;
    policy.primary_limit = primary_limit;
    policy.total_limit = total_limit;
    policy.graph_seed_limit = 0;
    policy.graph_neighbors_per_seed = 0;
    if (elpis_hybrid_policy_validate(&policy) != 0) {
        snprintf(error_buf, 256, "policy invalid"); return -1;
    }

    elpis_hybrid_retriever *retriever = NULL;
    if (elpis_hybrid_retriever_create(env->corpus, env->index, NULL, &policy, &retriever) != 0) {
        snprintf(error_buf, 256, "retriever_create failed"); return -1;
    }

    elpis_hybrid_query q;
    memset(&q, 0, sizeof q);
    q.text = query_text;
    q.vector = query_vector;
    q.dimensions = (uint32_t)query_dim;
    q.namespace_filter = NULL;
    q.authority_filter = NULL;

    elpis_retrieval_bundle *bundle = NULL;
    int rc = elpis_hybrid_retrieve(retriever, &q, &bundle);
    if (rc != 0) {
        snprintf(error_buf, 256, "retrieve rc=%d", rc);
        elpis_hybrid_retriever_destroy(retriever);
        return rc;
    }

    char *j = NULL;
    char bd[65];
    if (elpis_retrieval_bundle_json(bundle, &j, bd) != 0) {
        snprintf(error_buf, 256, "bundle_json failed");
        elpis_retrieval_bundle_destroy(bundle);
        elpis_hybrid_retriever_destroy(retriever);
        return -1;
    }

    size_t jlen = strlen(j);
    if (jlen >= (size_t)bundle_json_cap) jlen = bundle_json_cap - 1;
    memcpy(bundle_json_out, j, jlen);
    bundle_json_out[jlen] = '\0';
    elpis_free(j);

    memcpy(bundle_digest_out, bd, 64);
    bundle_digest_out[64] = '\0';

    char qd[65], cmd[65], vid[65], gsd[65], fpd[65], hpd[65];
    elpis_retrieval_bundle_identity(bundle, qd, cmd, vid, gsd, fpd, bd, hpd);
    if (query_digest_out)      { memcpy(query_digest_out, qd, 64); query_digest_out[64] = '\0'; }
    if (corpus_manifest_digest_out) { memcpy(corpus_manifest_digest_out, cmd, 64); corpus_manifest_digest_out[64] = '\0'; }
    if (vindex_manifest_digest_out) { memcpy(vindex_manifest_digest_out, vid, 64); vindex_manifest_digest_out[64] = '\0'; }
    if (fusion_policy_digest_out)   { memcpy(fusion_policy_digest_out, fpd, 64); fusion_policy_digest_out[64] = '\0'; }

    if (item_count_out) *item_count_out = (int)elpis_retrieval_bundle_item_count(bundle);

    elpis_retrieval_bundle_destroy(bundle);
    elpis_hybrid_retriever_destroy(retriever);
    snprintf(error_buf, 256, "ok");
    return 0;
}

const char *r1_env_corpus_digest(r1_env_t *env) { return env ? env->corpus_digest : ""; }
const char *r1_env_shard_digest(r1_env_t *env) { return env ? env->shard_digest : ""; }
const char *r1_env_corpus_manifest(r1_env_t *env) { return env ? env->corpus_manifest_json : ""; }
const char *r1_env_vindex_manifest(r1_env_t *env) { return env ? env->vindex_manifest_json : ""; }
