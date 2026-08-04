/* test_vector_search.cpp - Gate R2.3 exact search suite. */
#include "r2_test_support.h"

#include "elpis/vector_index.h"
#include "elpis/vector_result.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

static int fails = 0, checks = 0;
static const char *cur = "?";
#define CHECK(cond, ...) do { checks++; if (!(cond)) { \
        std::printf("  FAIL [%s] %s:%d ", cur, __FILE__, __LINE__); std::printf(__VA_ARGS__); \
        std::putchar('\n'); fails++; } } while (0)
#define CASE(name) do { cur = (name); std::printf("- %s\n", cur); } while (0)

static const uint32_t D = ELPIS_EMBEDDING_DIM;
static std::string base;
static const char *kCorpusDg = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

struct Env {
    fms_ctx *fms = nullptr;
    elpis_embedder *emb = nullptr;
    elpis_vector_index *ix = nullptr;
    elpis_embedding_profile profile{};
    ~Env() {
        if (ix) elpis_vector_index_destroy(ix);
        if (fms) fms_destroy(fms);
        if (emb) elpis_embedder_destroy(emb);
    }
};

static bool env_up(Env &e, const std::string &sub, uint64_t warm = 8ull << 20) {
    e.fms = r2t::make_fms(base + "/" + sub, warm);
    if (!e.fms) return false;
    if (elpis_embedder_fixture_create(ELPIS_NORM_L2, &e.emb) != 0) return false;
    elpis_embedder_profile(e.emb, &e.profile);
    return elpis_vector_index_create(e.fms, &e.profile, kCorpusDg, &e.ix) == 0;
}

/* ------------------------------------------------------------------ cases -- */

static void case_known_neighbour() {
    CASE("exact nearest neighbour and score correctness");
    Env e;
    if (!env_up(e, "nn")) { CHECK(false, "env"); return; }
    r2t::Corpus c;
    c.build("nn", 64, e.emb);
    char sd[65];
    std::vector<uint8_t> img = r2t::build_shard(c, kCorpusDg, sd);
    CHECK(elpis_vector_index_add_shard_bytes(e.ix, img.data(), img.size(), nullptr) == 0,
          "admit: %s", elpis_vector_index_error(e.ix));

    /* Query with an exact copy of record 17's vector. */
    const uint32_t target = 17;
    elpis_vector_query q;
    std::memset(&q, 0, sizeof q);
    q.vector = c.vec[target].data();
    q.dimensions = D;
    q.k = 5;
    std::vector<elpis_vector_hit> hits(q.k);
    uint32_t n = 0;
    CHECK(elpis_vector_index_search(e.ix, &q, hits.data(), &n) == 0, "search: %s",
          elpis_vector_index_error(e.ix));
    CHECK(n == 5, "expected 5 hits, got %u", n);
    if (n) {
        CHECK(hits[0].chunk_digest == c.chunk[target], "nearest neighbour is not the query itself");
        /* The fixture construction is exactly normalized with power-of-two
         * components, so self-similarity is exactly 1.0 and its canonical key
         * is exactly the full scale. */
        CHECK(hits[0].score == 1.0, "self-similarity %.17g, expected exactly 1.0", hits[0].score);
        CHECK(hits[0].score_key == ELPIS_VEC_SCORE_SCALE,
              "self score_key %lld, expected %lld", (long long)hits[0].score_key,
              (long long)ELPIS_VEC_SCORE_SCALE);
        CHECK(hits[0].rank == 0, "rank not assigned");
        CHECK(hits[0].doc_digest == c.doc[target], "document digest mismatch");
        CHECK(std::strcmp(hits[0].shard_digest, sd) == 0, "shard digest not reported");
        CHECK(std::strlen(hits[0].embedding_profile_digest) == 64, "profile digest not reported");
    }
    for (uint32_t i = 1; i < n; i++) {
        CHECK(hits[i - 1].score_key >= hits[i].score_key, "score keys not descending at %u", i);
        if (hits[i - 1].score_key == hits[i].score_key)
            CHECK(std::strcmp(hits[i - 1].chunk_digest, hits[i].chunk_digest) < 0,
                  "tie at %u not broken by ascending chunk digest", i);
    }

    /* Independent oracle: reproduce the declared cosine exactly as documented,
     * double accumulation, index-order summation, query normalized first. The
     * stored float32 vectors have |v| within 1e-8 of 1, so a raw dot product is
     * NOT the same quantity and must not be used as the oracle. */
    {
        std::vector<float> qn = c.vec[target];
        CHECK(elpis_vector_l2_normalize(qn.data(), D) == 0, "oracle query normalize");
        double qnorm = elpis_vector_l2_norm(qn.data(), D);
        for (uint32_t i = 0; i < n; i++) {
            size_t src = 0;
            while (src < c.chunk.size() && c.chunk[src] != hits[i].chunk_digest) src++;
            CHECK(src < c.chunk.size(), "hit %u not in the corpus", i);
            if (src >= c.chunk.size()) continue;
            double dot = 0.0, vsq = 0.0;
            for (uint32_t d = 0; d < D; d++) {
                double v = (double)c.vec[src][d];
                dot += v * (double)qn[d];
                vsq += v * v;
            }
            double expect = dot / (std::sqrt(vsq) * qnorm);
            /* Identity is the canonical key, not the raw double. */
            CHECK(elpis_vector_score_key(expect) == hits[i].score_key,
                  "score_key drift at rank %u: kernel %lld oracle %lld (%.17g vs %.17g)", i,
                  (long long)hits[i].score_key, (long long)elpis_vector_score_key(expect),
                  hits[i].score, expect);
        }
    }
}

static void case_determinism_and_ties() {
    CASE("deterministic top-k and digest tie-breaking");
    Env e;
    if (!env_up(e, "ties")) { CHECK(false, "env"); return; }
    r2t::Corpus c;
    c.build("ties", 32, e.emb);
    /* Force an exact tie: three records share one vector. */
    c.vec[5] = c.vec[1];
    c.vec[9] = c.vec[1];
    c.refresh();
    char sd[65];
    std::vector<uint8_t> img = r2t::build_shard(c, kCorpusDg, sd);
    CHECK(elpis_vector_index_add_shard_bytes(e.ix, img.data(), img.size(), nullptr) == 0, "admit");

    elpis_vector_query q;
    std::memset(&q, 0, sizeof q);
    q.vector = c.vec[1].data();
    q.dimensions = D;
    q.k = 4;
    std::vector<elpis_vector_hit> h1(q.k), h2(q.k);
    uint32_t n1 = 0, n2 = 0;
    elpis_vector_index_search(e.ix, &q, h1.data(), &n1);
    elpis_vector_index_search(e.ix, &q, h2.data(), &n2);

    char d1[65], d2[65];
    elpis_vector_result_digest(h1.data(), n1, d1);
    elpis_vector_result_digest(h2.data(), n2, d2);
    CHECK(n1 == n2 && std::strcmp(d1, d2) == 0, "repeated identical queries gave different results");

    CHECK(n1 >= 3, "expected at least the three tied hits, got %u", n1);
    if (n1 >= 3) {
        std::vector<std::string> tied = {c.chunk[1], c.chunk[5], c.chunk[9]};
        std::sort(tied.begin(), tied.end());
        for (int i = 0; i < 3; i++) {
            CHECK(h1[(uint32_t)i].score_key == ELPIS_VEC_SCORE_SCALE,
                  "tied score_key %lld", (long long)h1[(uint32_t)i].score_key);
            CHECK(h1[(uint32_t)i].chunk_digest == tied[(size_t)i],
                  "tie at rank %d broken out of digest order", i);
        }
    }
}

static void case_multi_shard_order() {
    CASE("multiple shards, admission order does not affect ranking");
    r2t::Corpus a, b;
    char sda[65], sdb[65];
    std::vector<uint8_t> ia, ib;
    std::vector<float> query(D);
    {
        Env seed;
        if (!env_up(seed, "seed")) { CHECK(false, "env"); return; }
        a.build("shard-a", 24, seed.emb);
        b.build("shard-b", 24, seed.emb);
        ia = r2t::build_shard(a, kCorpusDg, sda);
        ib = r2t::build_shard(b, kCorpusDg, sdb);
        query = b.vec[7];
    }

    char forward[65] = {0}, reverse[65] = {0};
    for (int pass = 0; pass < 2; pass++) {
        Env e;
        if (!env_up(e, pass ? "multi-r" : "multi-f")) { CHECK(false, "env"); return; }
        if (pass == 0) {
            CHECK(elpis_vector_index_add_shard_bytes(e.ix, ia.data(), ia.size(), nullptr) == 0, "add a");
            CHECK(elpis_vector_index_add_shard_bytes(e.ix, ib.data(), ib.size(), nullptr) == 0, "add b");
        } else {
            CHECK(elpis_vector_index_add_shard_bytes(e.ix, ib.data(), ib.size(), nullptr) == 0, "add b");
            CHECK(elpis_vector_index_add_shard_bytes(e.ix, ia.data(), ia.size(), nullptr) == 0, "add a");
        }
        CHECK(elpis_vector_index_shard_count(e.ix) == 2, "shard count");

        elpis_vector_query q;
        std::memset(&q, 0, sizeof q);
        q.vector = query.data();
        q.dimensions = D;
        q.k = 8;
        std::vector<elpis_vector_hit> hits(q.k);
        uint32_t n = 0;
        CHECK(elpis_vector_index_search(e.ix, &q, hits.data(), &n) == 0, "search");
        CHECK(n == 8, "hits %u", n);
        elpis_vector_result_digest(hits.data(), n, pass ? reverse : forward);
        if (pass == 0 && n) CHECK(hits[0].chunk_digest == b.chunk[7], "wrong nearest across shards");

        /* Listing is sorted, so it too is admission-order independent. */
        char ids[2][65];
        uint32_t m = 0;
        CHECK(elpis_vector_index_list_shards(e.ix, ids, 2, &m) == 0 && m == 2, "list");
        if (m == 2) CHECK(std::strcmp(ids[0], ids[1]) < 0, "shard listing not sorted");
    }
    CHECK(std::strcmp(forward, reverse) == 0,
          "admission order changed the result digest:\n      %s\n      %s", forward, reverse);
}

static void case_duplicate_across_shards() {
    CASE("duplicate chunk digests across shards are rejected, never deduplicated silently");
    Env e;
    if (!env_up(e, "dup")) { CHECK(false, "env"); return; }
    r2t::Corpus a;
    a.build("dup-a", 12, e.emb);
    char sda[65];
    std::vector<uint8_t> ia = r2t::build_shard(a, kCorpusDg, sda);
    CHECK(elpis_vector_index_add_shard_bytes(e.ix, ia.data(), ia.size(), nullptr) == 0, "add a");

    /* Shard B reuses one chunk digest from shard A. */
    r2t::Corpus b;
    b.build("dup-b", 12, e.emb);
    b.chunk[3] = a.chunk[5];
    b.refresh();
    char sdb[65];
    std::vector<uint8_t> ib = r2t::build_shard(b, kCorpusDg, sdb);
    CHECK(elpis_vector_index_add_shard_bytes(e.ix, ib.data(), ib.size(), nullptr) ==
              ELPIS_VEC_E_DUPLICATE, "overlapping shard not reported as a duplicate");
    CHECK(std::strstr(elpis_vector_index_error(e.ix), "duplicate_chunk_digest") != nullptr,
          "wrong rejection reason: %s", elpis_vector_index_error(e.ix));
    CHECK(elpis_vector_index_shard_count(e.ix) == 1, "rejected shard left behind");

    /* Re-admitting the same shard is also refused. */
    CHECK(elpis_vector_index_add_shard_bytes(e.ix, ia.data(), ia.size(), nullptr) ==
              ELPIS_VEC_E_DUPLICATE, "re-admission not reported as a duplicate");

    /* No duplicate hits can therefore appear. */
    elpis_vector_query q;
    std::memset(&q, 0, sizeof q);
    q.vector = a.vec[5].data();
    q.dimensions = D;
    q.k = 12;
    std::vector<elpis_vector_hit> hits(q.k);
    uint32_t n = 0;
    elpis_vector_index_search(e.ix, &q, hits.data(), &n);
    for (uint32_t i = 1; i < n; i++)
        CHECK(std::strcmp(hits[i - 1].chunk_digest, hits[i].chunk_digest) != 0,
              "duplicate chunk digest in results at %u", i);
}

static void case_k_edges_and_bad_queries() {
    CASE("k = 0, k > candidates, and invalid queries");
    Env e;
    if (!env_up(e, "edges")) { CHECK(false, "env"); return; }
    r2t::Corpus c;
    c.build("edges", 6, e.emb);
    char sd[65];
    std::vector<uint8_t> img = r2t::build_shard(c, kCorpusDg, sd);
    elpis_vector_index_add_shard_bytes(e.ix, img.data(), img.size(), nullptr);

    elpis_vector_query q;
    std::memset(&q, 0, sizeof q);
    q.vector = c.vec[0].data();
    q.dimensions = D;
    std::vector<elpis_vector_hit> hits(64);
    uint32_t n = 99;

    q.k = 0;
    CHECK(elpis_vector_index_search(e.ix, &q, hits.data(), &n) == ELPIS_VEC_OK && n == 0,
          "k=0 not empty (%u)", n);

    q.k = 50;
    CHECK(elpis_vector_index_search(e.ix, &q, hits.data(), &n) == 0, "k > candidates failed");
    CHECK(n == 6, "k > candidates returned %u, expected 6", n);

    /* Zero-vector query under an L2/cosine profile is refused, not scored. */
    std::vector<float> zero(D, 0.0f);
    q.k = 3;
    q.vector = zero.data();
    CHECK(elpis_vector_index_search(e.ix, &q, hits.data(), &n) == ELPIS_VEC_E_QUERY,
          "zero-norm query not reported as a query error");

    /* Non-finite query. */
    std::vector<float> nanv = c.vec[0];
    nanv[2] = std::nanf("");
    q.vector = nanv.data();
    CHECK(elpis_vector_index_search(e.ix, &q, hits.data(), &n) == ELPIS_VEC_E_QUERY,
          "NaN query not reported as a query error");

    /* Wrong dimensions. */
    q.vector = c.vec[0].data();
    q.dimensions = 128;
    CHECK(elpis_vector_index_search(e.ix, &q, hits.data(), &n) == ELPIS_VEC_E_QUERY,
          "wrong query dimension not reported as a query error");
}

static void case_filters() {
    CASE("namespace and authority filtering, no leakage");
    Env e;
    if (!env_up(e, "filters")) { CHECK(false, "env"); return; }
    r2t::Corpus c;
    c.build("filters", 48, e.emb);
    char sd[65];
    std::vector<uint8_t> img = r2t::build_shard(c, kCorpusDg, sd);
    elpis_vector_index_add_shard_bytes(e.ix, img.data(), img.size(), nullptr);

    elpis_vector_query q;
    std::memset(&q, 0, sizeof q);
    q.vector = c.vec[0].data();     /* record 0 is elpis.code / canonical */
    q.dimensions = D;
    q.k = 48;
    std::vector<elpis_vector_hit> hits(48);
    uint32_t n = 0;

    elpis_vector_index_search(e.ix, &q, hits.data(), &n);
    CHECK(n == 48, "unfiltered search returned %u", n);

    q.ns_filter = "elpis.docs";
    elpis_vector_index_search(e.ix, &q, hits.data(), &n);
    CHECK(n == 24, "namespace filter returned %u, expected 24", n);
    for (uint32_t i = 0; i < n; i++)
        CHECK(std::strcmp(hits[i].ns, "elpis.docs") == 0, "namespace leak: %s", hits[i].ns);
    for (uint32_t i = 0; i < n; i++)
        CHECK(hits[i].chunk_digest != c.chunk[0], "excluded query chunk leaked into results");

    q.ns_filter = nullptr;
    q.authority_filter = "canonical";
    elpis_vector_index_search(e.ix, &q, hits.data(), &n);
    CHECK(n == 16, "authority filter returned %u, expected 16", n);
    for (uint32_t i = 0; i < n; i++)
        CHECK(std::strcmp(hits[i].authority, "canonical") == 0, "authority leak: %s", hits[i].authority);

    q.ns_filter = "elpis.docs";
    q.authority_filter = "canonical";
    elpis_vector_index_search(e.ix, &q, hits.data(), &n);
    CHECK(n == 8, "combined filter returned %u, expected 8", n);
    for (uint32_t i = 0; i < n; i++)
        CHECK(std::strcmp(hits[i].ns, "elpis.docs") == 0 &&
              std::strcmp(hits[i].authority, "canonical") == 0, "combined filter leak");

    q.ns_filter = "does.not.exist";
    q.authority_filter = nullptr;
    elpis_vector_index_search(e.ix, &q, hits.data(), &n);
    CHECK(n == 0, "unknown namespace returned %u hits", n);

    /* Filtering must not change the relative order of what survives. */
    q.ns_filter = "elpis.docs";
    elpis_vector_index_search(e.ix, &q, hits.data(), &n);
    for (uint32_t i = 1; i < n; i++)
        CHECK(elpis_vector_hit_compare(&hits[i - 1], &hits[i]) <= 0, "filtered order broken at %u", i);
}

static void case_index_manifest() {
    CASE("index manifest is canonical and content-addressed");
    Env e;
    if (!env_up(e, "manifest")) { CHECK(false, "env"); return; }
    r2t::Corpus a, b;
    a.build("m-a", 8, e.emb);
    b.build("m-b", 8, e.emb);
    char sda[65], sdb[65];
    std::vector<uint8_t> ia = r2t::build_shard(a, kCorpusDg, sda);
    std::vector<uint8_t> ib = r2t::build_shard(b, kCorpusDg, sdb);
    elpis_vector_index_add_shard_bytes(e.ix, ia.data(), ia.size(), nullptr);
    elpis_vector_index_add_shard_bytes(e.ix, ib.data(), ib.size(), nullptr);

    char *j1 = nullptr, *j2 = nullptr;
    char d1[65], d2[65];
    CHECK(elpis_vector_index_manifest_json(e.ix, &j1, d1) == 0, "manifest");
    CHECK(elpis_vector_index_manifest_json(e.ix, &j2, d2) == 0, "manifest again");
    CHECK(j1 && j2 && std::strcmp(j1, j2) == 0, "index manifest not byte-stable");
    CHECK(std::strcmp(d1, d2) == 0, "index manifest digest not stable");
    CHECK(std::strstr(j1, "\"abi_version\":") == j1 + 1, "keys not canonical");
    CHECK(std::strstr(j1, sda) && std::strstr(j1, sdb), "shard digests missing");
    CHECK(std::strstr(j1, "\"vector_count\":16"), "aggregate vector count wrong: %s", j1);
    CHECK(std::strchr(j1, '.') == nullptr, "floating point in an identity-bearing manifest");
    std::free(j1);
    std::free(j2);
}

int main(int argc, char **argv) {
    base = argc > 1 ? argv[1] : "/tmp/hacf-r2-search";
    r2t::rmtree(base);
    r2t::mkdirp(base);
    std::printf("R2 exact search suite, root=%s\n", base.c_str());

    case_known_neighbour();
    case_determinism_and_ties();
    case_multi_shard_order();
    case_duplicate_across_shards();
    case_k_edges_and_bad_queries();
    case_filters();
    case_index_manifest();

    std::printf("%d checks, %d failures\n", checks, fails);
    return fails != 0;
}
