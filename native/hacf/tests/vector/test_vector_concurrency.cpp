/* test_vector_concurrency.cpp - concurrent read-only dense search.
 * Run under ThreadSanitizer as well as the functional suite. */
#include "r2_test_support.h"

#include "elpis/vector_index.h"
#include "elpis/vector_result.h"

#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

static const uint32_t D = ELPIS_EMBEDDING_DIM;
static const char *kCorpusDg = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";

static std::atomic<int> g_fail{0};
static std::mutex g_io;

static void report(const char *what, const std::string &detail) {
    std::lock_guard<std::mutex> lk(g_io);
    std::printf("  FAIL %s: %s\n", what, detail.c_str());
    g_fail.store(1);
}

int main(int argc, char **argv) {
    std::string base = argc > 1 ? argv[1] : "/tmp/hacf-r2-conc";
    r2t::rmtree(base);
    r2t::mkdirp(base);
    std::printf("R2 concurrent search suite, root=%s\n", base.c_str());

    /* Deliberately tight: four ~800 KiB shards against a 2 MiB ceiling, so
     * queries race each other through promotion and demotion. */
    const uint64_t warm = 2ull << 20;
    fms_ctx *fms = r2t::make_fms(base + "/cold", warm);
    if (!fms) { std::printf("  FAIL fms\n"); return 1; }

    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile prof;
    elpis_embedder_profile(emb, &prof);

    elpis_vector_index *ix = nullptr;
    if (elpis_vector_index_create(fms, &prof, kCorpusDg, &ix) != 0) { std::printf("  FAIL index\n"); return 1; }

    std::vector<r2t::Corpus> shards(4);
    for (int i = 0; i < 4; i++) {
        char tag[32];
        std::snprintf(tag, sizeof tag, "conc-%d", i);
        shards[(size_t)i].build(tag, 384, emb);
        char sd[65];
        std::vector<uint8_t> img = r2t::build_shard(shards[(size_t)i], kCorpusDg, sd);
        if (elpis_vector_index_add_shard_bytes(ix, img.data(), img.size(), nullptr) != 0) {
            std::printf("  FAIL admit %d: %s\n", i, elpis_vector_index_error(ix));
            return 1;
        }
    }

    /* Single-threaded reference results for four distinct queries. */
    struct Q { std::vector<float> v; std::string digest; };
    std::vector<Q> queries(4);
    for (int i = 0; i < 4; i++) {
        queries[(size_t)i].v = shards[(size_t)i].vec[(size_t)(i * 7 + 3)];
        elpis_vector_query q;
        std::memset(&q, 0, sizeof q);
        q.vector = queries[(size_t)i].v.data();
        q.dimensions = D;
        q.k = 8;
        std::vector<elpis_vector_hit> hits(q.k);
        uint32_t n = 0;
        if (elpis_vector_index_search(ix, &q, hits.data(), &n) != 0 || n != 8) {
            std::printf("  FAIL reference search %d\n", i);
            return 1;
        }
        char dg[65];
        elpis_vector_result_digest(hits.data(), n, dg);
        queries[(size_t)i].digest = dg;
    }

    /* Iteration count is overridable purely for runtime attribution: scaling it
     * and observing linear runtime distinguishes per-operation cost from a
     * fixed stall such as a residency deadline. The default is unchanged and is
     * what CTest runs. */
    const int threads = 4;
    int iters = 60;
    if (const char *e = std::getenv("ELPIS_R2_CONC_ITERS")) {
        int v = std::atoi(e);
        if (v > 0 && v <= 10000) iters = v;
    }
    std::vector<std::thread> pool;
    for (int t = 0; t < threads; t++) {
        pool.emplace_back([&, t]() {
            for (int it = 0; it < iters; it++) {
                const Q &qq = queries[(size_t)((t + it) % 4)];
                elpis_vector_query q;
                std::memset(&q, 0, sizeof q);
                q.vector = qq.v.data();
                q.dimensions = D;
                q.k = 8;
                elpis_vector_hit hits[8];
                uint32_t n = 0;
                int rc = elpis_vector_index_search(ix, &q, hits, &n);
                if (rc != 0) { report("search", elpis_vector_index_error(ix)); return; }
                if (n != 8) { report("hit count", std::to_string(n)); return; }
                char dg[65];
                elpis_vector_result_digest(hits, n, dg);
                if (qq.digest != dg)
                    report("result digest diverged under concurrency", std::string(dg) + " != " + qq.digest);
                for (uint32_t i = 1; i < n; i++)
                    if (elpis_vector_hit_compare(&hits[i - 1], &hits[i]) > 0)
                        report("ordering", "hits out of order");
            }
        });
    }
    /* A pump thread demotes underneath the readers the whole time. */
    std::thread pumper([&]() {
        for (int i = 0; i < iters * threads; i++) {
            fms_pump(fms);
            fms_stats st;
            fms_get_stats(fms, &st);
            if (st.domain_bytes[FMS_DOM_RAM] > warm)
                report("ram ceiling", std::to_string(st.domain_bytes[FMS_DOM_RAM]));
            if (st.tier_bytes[FMS_HOT] != 0) report("hot residency", "HOT tier used");
        }
    });
    for (auto &th : pool) th.join();
    pumper.join();

    fms_stats st;
    fms_get_stats(fms, &st);
    if (st.pinned_bytes != 0) report("pin leak", std::to_string(st.pinned_bytes));
    if (st.inflight_ops != 0) report("inflight leak", std::to_string(st.inflight_ops));
    if (st.digest_failures != 0) report("digest failures", std::to_string(st.digest_failures));

    uint32_t shard_n = 0;
    elpis_vector_index_list_shards(ix, nullptr, 0, &shard_n);
    if (shard_n != 4) report("shard count", std::to_string(shard_n));

    std::printf("threads=%d iters=%d promotions=%llu demotions=%llu bytes_promoted=%llu "
                "bytes_demoted=%llu ram_peak_ok=%s\n",
                threads, iters, (unsigned long long)st.promotions,
                (unsigned long long)st.demotions, (unsigned long long)st.bytes_promoted,
                (unsigned long long)st.bytes_demoted,
                st.domain_bytes[FMS_DOM_RAM] <= warm ? "yes" : "no");

    elpis_vector_index_destroy(ix);
    fms_get_stats(fms, &st);
    if (st.objects != 0) report("object leak", std::to_string(st.objects));
    fms_destroy(fms);
    elpis_embedder_destroy(emb);

    std::printf(g_fail.load() ? "RESULT: concurrency failures\n" : "RESULT: concurrent search clean\n");
    return g_fail.load();
}
