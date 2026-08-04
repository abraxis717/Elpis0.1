/* test_fms_concurrency.c - concurrent retrieval-style access to one context.
 * Run under ThreadSanitizer and AddressSanitizer. */
#define _POSIX_C_SOURCE 200809L

#include "elpis/fms.h"
#include "elpis/fms_pal_test.h"

#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MB       (1024ull * 1024ull)
#define N_OBJ    12
#define OBJ_SZ   (256u * 1024u)
#define N_THREAD 4
#define N_ITER   400

static fms_ctx *g_ctx;
static fms_id   g_id[N_OBJ];
static unsigned char g_val[N_OBJ];
static volatile int g_fail;

static void fail(const char *msg, int i) {
    fprintf(stderr, "FAIL %s (obj %d)\n", msg, i);
    __atomic_store_n(&g_fail, 1, __ATOMIC_SEQ_CST);
}

static void *worker(void *arg) {
    uint32_t rng = (uint32_t)(uintptr_t)arg * 2654435761u + 1u;
    for (int it = 0; it < N_ITER; it++) {
        rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
        int i = (int)(rng % N_OBJ);
        void *p = NULL;
        int r = fms_acquire(g_ctx, g_id[i], FMS_WARM, FMS_READ, &p);
        if (r < 0) {
            if (r != FMS_E_BUSY && r != FMS_E_LIMIT) fail("acquire", i);
            continue;
        }
        const unsigned char *b = (const unsigned char *)p;
        for (unsigned k = 0; k < OBJ_SZ; k += 1021)
            if (b[k] != g_val[i]) { fail("corruption", i); break; }
        fms_release(g_ctx, g_id[i]);
        if ((it & 15) == 0) fms_touch(g_ctx, g_id[i]);
    }
    return NULL;
}

static void *pumper(void *arg) {
    (void)arg;
    for (int i = 0; i < N_ITER * 2; i++) {
        fms_pump(g_ctx);
        fms_stats st;
        fms_get_stats(g_ctx, &st);
        if (st.domain_bytes[FMS_DOM_RAM] > 2 * MB) { fail("ram ceiling breached", -1); break; }
    }
    return NULL;
}

int main(int argc, char **argv) {
    const char *root = argc > 1 ? argv[1] : "/tmp/elpis-fms-conc";
    fms_pal_test_opts o;
    memset(&o, 0, sizeof o);
    o.cold_root = root;

    fms_config cfg;
    memset(&cfg, 0, sizeof cfg);
    cfg.tier_budget[FMS_WARM] = 2 * MB;
    cfg.tier_budget[FMS_COLD] = 64 * MB;
    cfg.domain_ceiling[FMS_DOM_RAM] = 2 * MB;
    cfg.domain_ceiling[FMS_DOM_DEVICE] = 1;
    cfg.domain_ceiling[FMS_DOM_STORAGE] = 64 * MB;
    cfg.high_wm = 0.90f; cfg.low_wm = 0.70f;
    cfg.max_objects = 32;

    g_ctx = fms_create(&cfg, fms_pal_test_create(&o));
    if (!g_ctx) { fprintf(stderr, "FAIL create\n"); return 1; }

    unsigned char *buf = malloc(OBJ_SZ);
    for (int i = 0; i < N_OBJ; i++) {
        g_val[i] = (unsigned char)(i * 7 + 1);
        memset(buf, g_val[i], OBJ_SZ);
        if (fms_register(g_ctx, 1, OBJ_SZ, FMS_WARM, 0.0f, buf, &g_id[i]) < 0) {
            fprintf(stderr, "FAIL register %d\n", i);
            return 1;
        }
    }
    free(buf);

    pthread_t th[N_THREAD + 1];
    for (long t = 0; t < N_THREAD; t++) pthread_create(&th[t], NULL, worker, (void *)(t + 1));
    pthread_create(&th[N_THREAD], NULL, pumper, NULL);
    for (int t = 0; t <= N_THREAD; t++) pthread_join(th[t], NULL);

    fms_stats st;
    fms_get_stats(g_ctx, &st);
    if (st.inflight_ops != 0) { fprintf(stderr, "FAIL inflight leak\n"); g_fail = 1; }
    if (st.pinned_bytes != 0) { fprintf(stderr, "FAIL pin leak: %llu\n",
                                        (unsigned long long)st.pinned_bytes); g_fail = 1; }
    if (st.domain_bytes[FMS_DOM_RAM] > 2 * MB) { fprintf(stderr, "FAIL final ram\n"); g_fail = 1; }
    printf("threads=%d iters=%d promotions=%llu demotions=%llu p50=%lluns p95=%lluns\n",
           N_THREAD, N_ITER, (unsigned long long)st.promotions,
           (unsigned long long)st.demotions, (unsigned long long)st.move_p50_ns,
           (unsigned long long)st.move_p95_ns);

    for (int i = 0; i < N_OBJ; i++) fms_unregister(g_ctx, g_id[i]);
    fms_destroy(g_ctx);
    printf(g_fail ? "RESULT: concurrency failures\n" : "RESULT: concurrent access clean\n");
    return g_fail;
}
