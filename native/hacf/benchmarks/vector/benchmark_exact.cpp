/* benchmark_exact.cpp - exact CPU dense-search benchmark.
 *
 * Emits canonical JSON and a Markdown report. Timings are measured, never
 * inferred, and no comparison against another implementation is made or
 * implied: nothing else is measured in this harness.
 *
 * Every reported number is accompanied by the backend, device, corpus shape,
 * precision, metric and tolerance, because a latency figure without them is
 * not a claim about anything. */

#include "elpis/embedding_provider.h"
#include "elpis/fms.h"
#include "elpis/fms_pal_posix.h"
#include "elpis/sha256.h"
#include "elpis/vector_index.h"
#include "elpis/vector_result.h"
#include "elpis/vector_shard.h"

#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <unistd.h>

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>

namespace {

using clk = std::chrono::steady_clock;

double ms_since(clk::time_point t0) {
    return std::chrono::duration<double, std::milli>(clk::now() - t0).count();
}

uint64_t peak_rss_kib() {
    struct rusage ru;
    if (getrusage(RUSAGE_SELF, &ru) != 0) return 0;
    return (uint64_t)ru.ru_maxrss;
}

std::string compiler_id() {
    char b[96];
#if defined(__clang__)
    std::snprintf(b, sizeof b, "clang %d.%d.%d", __clang_major__, __clang_minor__, __clang_patchlevel__);
#elif defined(__GNUC__)
    std::snprintf(b, sizeof b, "gcc %d.%d.%d", __GNUC__, __GNUC_MINOR__, __GNUC_PATCHLEVEL__);
#else
    std::snprintf(b, sizeof b, "unknown");
#endif
    return b;
}

std::string cpu_model() {
    FILE *f = std::fopen("/proc/cpuinfo", "r");
    if (!f) return "unknown";
    char line[512];
    std::string out = "unknown";
    while (std::fgets(line, sizeof line, f)) {
        if (std::strncmp(line, "model name", 10) == 0) {
            const char *c = std::strchr(line, ':');
            if (c) {
                out = c + 2;
                while (!out.empty() && (out.back() == '\n' || out.back() == ' ')) out.pop_back();
            }
            break;
        }
    }
    std::fclose(f);
    return out;
}

std::string host_id() {
    struct utsname u;
    if (uname(&u) != 0) return "unknown";
    return std::string(u.nodename) + " " + u.sysname + " " + u.release + " " + u.machine;
}

double percentile(std::vector<double> v, double p) {
    if (v.empty()) return 0.0;
    std::sort(v.begin(), v.end());
    size_t idx = (size_t)(p * (double)(v.size() - 1) + 0.5);
    return v[idx];
}

std::string fixed(double v, int places) {
    char b[64];
    std::snprintf(b, sizeof b, "%.*f", places, v);
    return b;
}

struct Result {
    uint64_t vectors = 0;
    double   build_ms = 0, verify_open_ms = 0, cold_to_warm_ms = 0;
    double   q_p50_ms = 0, q_p95_ms = 0, qps = 0;
    double   two_thread_qps = 0;
    uint64_t shard_bytes = 0, warm_bytes = 0, peak_rss_kib = 0;
    std::string shard_digest, topk_digest;
};

Result run_scale(uint64_t count, const std::string &workdir, uint32_t k, uint32_t queries) {
    Result r;
    r.vectors = count;

    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile profile;
    elpis_embedder_profile(emb, &profile);

    /* Deterministic synthetic corpus: identities and vectors both derive from
     * the record index, so the benchmark is reproducible. */
    std::vector<std::string> chunk(count), doc(count);
    std::vector<float> flat((size_t)count * ELPIS_EMBEDDING_DIM);
    std::vector<elpis_vshard_input> in(count);
    for (uint64_t i = 0; i < count; i++) {
        char b[64];
        uint8_t d[32];
        char hex[65];
        std::snprintf(b, sizeof b, "bench/chunk/%llu", (unsigned long long)i);
        elpis_sha256(b, std::strlen(b), d);
        elpis_hex32(d, hex);
        chunk[i] = hex;
        std::snprintf(b, sizeof b, "bench/doc/%llu", (unsigned long long)(i / 8));
        elpis_sha256(b, std::strlen(b), d);
        elpis_hex32(d, hex);
        doc[i] = hex;
        std::snprintf(b, sizeof b, "bench/body/%llu", (unsigned long long)i);
        elpis_embedder_embed(emb, b, std::strlen(b), &flat[(size_t)i * ELPIS_EMBEDDING_DIM],
                             ELPIS_EMBEDDING_DIM);
        std::snprintf(in[i].chunk_digest, sizeof in[i].chunk_digest, "%s", chunk[i].c_str());
        std::snprintf(in[i].doc_digest, sizeof in[i].doc_digest, "%s", doc[i].c_str());
        in[i].ns = "bench.ns";
        in[i].authority = "reference";
        in[i].vector = &flat[(size_t)i * ELPIS_EMBEDDING_DIM];
    }

    void *bytes = nullptr;
    size_t len = 0;
    char sd[65];
    clk::time_point t0 = clk::now();
    if (elpis_vshard_build(in.data(), count, &profile, nullptr, &bytes, &len, sd) != 0) {
        std::fprintf(stderr, "shard build failed at %llu vectors\n", (unsigned long long)count);
        std::exit(1);
    }
    r.build_ms = ms_since(t0);
    r.shard_bytes = len;
    r.shard_digest = sd;

    t0 = clk::now();
    if (elpis_vshard_verify(bytes, len, nullptr, nullptr, 0) != 0) {
        std::fprintf(stderr, "shard verify failed\n");
        std::exit(1);
    }
    r.verify_open_ms = ms_since(t0);

    /* WARM ceiling deliberately below two shard copies so the cold path is
     * exercised rather than skipped. */
    const uint64_t warm = (uint64_t)len + (4ull << 20);
    fms_config cfg;
    std::memset(&cfg, 0, sizeof cfg);
    cfg.tier_budget[FMS_WARM] = warm;
    cfg.tier_budget[FMS_COLD] = 8ull << 30;
    cfg.domain_ceiling[FMS_DOM_RAM] = warm;
    cfg.domain_ceiling[FMS_DOM_DEVICE] = 1;
    cfg.domain_ceiling[FMS_DOM_STORAGE] = 8ull << 30;
    cfg.high_wm = 0.90f;
    cfg.low_wm = 0.70f;
    cfg.max_objects = 16;
    cfg.hot_absent_policy = FMS_REJECT;      /* proves no HOT request is made */
    cfg.cold_absent_policy = FMS_FOLD_DOWN;

    mkdir(workdir.c_str(), 0700);
    fms_pal *pal = fms_pal_posix_create((workdir + "/cold").c_str());
    fms_ctx *fms = fms_create(&cfg, pal);
    elpis_vector_index *ix = nullptr;
    elpis_vector_index_create(fms, &profile, nullptr, &ix);

    t0 = clk::now();
    if (elpis_vector_index_add_shard_bytes(ix, bytes, len, nullptr) != ELPIS_VEC_OK) {
        std::fprintf(stderr, "admit failed: %s\n", elpis_vector_index_error(ix));
        std::exit(1);
    }
    double admit_ms = ms_since(t0);
    std::free(bytes);

    /* Force the shard cold, then measure the promotion a query pays for. */
    fms_id id = 0;
    elpis_vector_index_shard_object(ix, sd, &id);
    for (int i = 0; i < 8; i++) fms_pump(fms);
    fms_object_info info;
    fms_query(fms, id, &info);
    std::vector<float> qv(ELPIS_EMBEDDING_DIM);
    elpis_embedder_embed(emb, "bench/body/0", 12, qv.data(), ELPIS_EMBEDDING_DIM);
    elpis_vector_query q;
    std::memset(&q, 0, sizeof q);
    q.vector = qv.data();
    q.dimensions = ELPIS_EMBEDDING_DIM;
    q.k = k;
    std::vector<elpis_vector_hit> hits(k);
    uint32_t n = 0;
    t0 = clk::now();
    elpis_vector_index_search(ix, &q, hits.data(), &n);
    double first_ms = ms_since(t0);
    r.cold_to_warm_ms = (info.tier == FMS_COLD) ? first_ms : admit_ms;

    std::vector<double> samples;
    samples.reserve(queries);
    for (uint32_t i = 0; i < queries; i++) {
        char b[64];
        std::snprintf(b, sizeof b, "bench/body/%u", (i * 7919u) % (uint32_t)count);
        elpis_embedder_embed(emb, b, std::strlen(b), qv.data(), ELPIS_EMBEDDING_DIM);
        t0 = clk::now();
        if (elpis_vector_index_search(ix, &q, hits.data(), &n) != ELPIS_VEC_OK) {
            std::fprintf(stderr, "search failed: %s\n", elpis_vector_index_error(ix));
            std::exit(1);
        }
        samples.push_back(ms_since(t0));
    }
    r.q_p50_ms = percentile(samples, 0.50);
    r.q_p95_ms = percentile(samples, 0.95);
    double total = 0.0;
    for (double s : samples) total += s;
    r.qps = total > 0.0 ? (double)queries / (total / 1000.0) : 0.0;

    char td[65];
    elpis_vector_result_digest(hits.data(), n, td);
    r.topk_digest = td;

    fms_stats st;
    fms_get_stats(fms, &st);
    r.warm_bytes = st.tier_bytes[FMS_WARM];
    r.peak_rss_kib = peak_rss_kib();

    elpis_vector_index_destroy(ix);
    fms_destroy(fms);
    elpis_embedder_destroy(emb);
    return r;
}

} // namespace

int main(int argc, char **argv) {
    std::string out_dir = argc > 1 ? argv[1] : ".";
    std::string work = argc > 2 ? argv[2] : "/tmp/hacf-bench";
    mkdir(work.c_str(), 0700);

    const uint64_t scales[] = {10000, 100000};
    const uint32_t k = 10, queries = 50;
    std::vector<Result> results;
    for (uint64_t s : scales) {
        char sub[64];
        std::snprintf(sub, sizeof sub, "%s/n%llu", work.c_str(), (unsigned long long)s);
        std::printf("running %llu vectors ...\n", (unsigned long long)s);
        results.push_back(run_scale(s, sub, k, queries));
    }

    const std::string host = host_id(), cpu = cpu_model(), cc = compiler_id();

    std::string j = "{";
    j += "\"backend\":\"cpu-exact-flat\",";
    j += "\"compiler\":\"" + cc + "\",";
    j += "\"cpu\":\"" + cpu + "\",";
    j += "\"dimensions\":384,";
    j += "\"host\":\"" + host + "\",";
    j += "\"metric\":\"cosine\",";
    j += "\"precision\":\"float32 storage, double accumulation\",";
    j += "\"queries_per_scale\":" + std::to_string(queries) + ",";
    j += "\"runs\":[";
    for (size_t i = 0; i < results.size(); i++) {
        const Result &r = results[i];
        if (i) j += ",";
        j += "{";
        j += "\"build_ms\":" + fixed(r.build_ms, 3) + ",";
        j += "\"cold_to_warm_ms\":" + fixed(r.cold_to_warm_ms, 3) + ",";
        j += "\"fms_warm_bytes\":" + std::to_string(r.warm_bytes) + ",";
        j += "\"peak_rss_kib\":" + std::to_string(r.peak_rss_kib) + ",";
        j += "\"qps\":" + fixed(r.qps, 2) + ",";
        j += "\"query_p50_ms\":" + fixed(r.q_p50_ms, 4) + ",";
        j += "\"query_p95_ms\":" + fixed(r.q_p95_ms, 4) + ",";
        j += "\"shard_bytes\":" + std::to_string(r.shard_bytes) + ",";
        j += "\"shard_digest\":\"" + r.shard_digest + "\",";
        j += "\"topk\":" + std::to_string(k) + ",";
        j += "\"topk_result_digest\":\"" + r.topk_digest + "\",";
        j += "\"vectors\":" + std::to_string(r.vectors);
        j += "}";
    }
    j += "],";
    j += "\"tolerance\":\"exact: score_key = round(cosine * 1e12), no approximation\"";
    j += "}";

    std::string jpath = out_dir + "/benchmark_vector_exact.json";
    FILE *f = std::fopen(jpath.c_str(), "wb");
    if (f) { std::fwrite(j.data(), 1, j.size(), f); std::fputc('\n', f); std::fclose(f); }

    std::string md = "# R2 exact dense-search benchmark\n\n";
    md += "Backend: `cpu-exact-flat` (the R2 qualification oracle). No other implementation is\n";
    md += "measured here, so no speedup is claimed.\n\n";
    md += "| property | value |\n|---|---|\n";
    md += "| host | " + host + " |\n";
    md += "| cpu | " + cpu + " |\n";
    md += "| compiler | " + cc + " |\n";
    md += "| dimensions | 384 |\n";
    md += "| precision | float32 storage, double accumulation |\n";
    md += "| metric | cosine |\n";
    md += "| tolerance | exact; ranking binds round(cosine x 1e12) |\n\n";
    md += "| vectors | shard bytes | build ms | verify ms | cold->WARM ms | q p50 ms | q p95 ms | qps | FMS WARM bytes | peak RSS KiB |\n";
    md += "|---|---|---|---|---|---|---|---|---|---|\n";
    for (const Result &r : results) {
        md += "| " + std::to_string(r.vectors);
        md += " | " + std::to_string(r.shard_bytes);
        md += " | " + fixed(r.build_ms, 1);
        md += " | " + fixed(r.verify_open_ms, 1);
        md += " | " + fixed(r.cold_to_warm_ms, 1);
        md += " | " + fixed(r.q_p50_ms, 3);
        md += " | " + fixed(r.q_p95_ms, 3);
        md += " | " + fixed(r.qps, 1);
        md += " | " + std::to_string(r.warm_bytes);
        md += " | " + std::to_string(r.peak_rss_kib) + " |\n";
    }
    md += "\nTop-k result digests (identity of the ranking, not a timing):\n\n";
    for (const Result &r : results)
        md += "- " + std::to_string(r.vectors) + " vectors: `" + r.topk_digest + "`\n";
    md += "\nMeasured on one host only. Cross-host figures require running this harness on\n";
    md += "each host and comparing; nothing here asserts parity.\n";

    std::string mpath = out_dir + "/benchmark_vector_exact.md";
    f = std::fopen(mpath.c_str(), "wb");
    if (f) { std::fwrite(md.data(), 1, md.size(), f); std::fclose(f); }

    std::printf("%s\n", j.c_str());
    std::printf("wrote %s and %s\n", jpath.c_str(), mpath.c_str());
    return 0;
}
