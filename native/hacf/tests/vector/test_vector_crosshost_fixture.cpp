/* test_vector_crosshost_fixture.cpp - committed cross-host determinism fixture.
 *
 * The whole pipeline runs from committed bytes: ingest -> chunk -> embed ->
 * shard -> admit -> query -> ranked result. Every identity it produces is
 * compared against tests/vector/fixture/expected.txt, which is committed.
 *
 * Running this on Ouroboros and on elpis-mba72 must produce byte-identical
 * values for all seven identities. This test does NOT by itself prove
 * cross-host parity: it is the instrument that the operator runs on both hosts
 * to establish it.
 *
 * ELPIS_R2_FIXTURE_REGENERATE=1 rewrites the expected file. That is only
 * legitimate when the embedding profile, chunking profile or shard ABI has
 * deliberately changed, and it invalidates every previously built shard. */
#include "r2_test_support.h"

#include "elpis/chunking.h"
#include "elpis/corpus.h"
#include "elpis/vector_index.h"
#include "elpis/vector_result.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <map>
#include <string>
#include <vector>

#ifndef HACF_FIXTURE_DIR
#define HACF_FIXTURE_DIR "tests/vector/fixture"
#endif

static int fails = 0, checks = 0;
static const char *cur = "?";
#define CHECK(cond, ...) do { checks++; if (!(cond)) { \
        std::printf("  FAIL [%s] %s:%d ", cur, __FILE__, __LINE__); std::printf(__VA_ARGS__); \
        std::putchar('\n'); fails++; } } while (0)
#define CASE(name) do { cur = (name); std::printf("- %s\n", cur); } while (0)

static const uint32_t D = ELPIS_EMBEDDING_DIM;
static const char *kQuery = "ELPIS_ROOT_A is the active root filesystem for the qualification host";
static const uint32_t kTopK = 5;

/* Files are ingested in this fixed order; origins are basenames so an absolute
 * build path can never enter a digest. */
static const char *kFiles[] = {"host.md", "kernel.c", "memory.md", "notes.txt"};
static const char *kMedia[] = {ELPIS_MT_MARKDOWN, ELPIS_MT_CODE, ELPIS_MT_MARKDOWN, ELPIS_MT_TEXT};
static const char *kNs[]    = {"elpis.docs", "elpis.code", "elpis.docs", "elpis.notes"};
static const char *kAuth[]  = {"canonical", "reference", "canonical", "advisory"};

static int read_file(const std::string &p, std::string &out) {
    FILE *f = std::fopen(p.c_str(), "rb");
    if (!f) return -1;
    char buf[4096];
    size_t n;
    out.clear();
    while ((n = std::fread(buf, 1, sizeof buf, f)) > 0) out.append(buf, n);
    std::fclose(f);
    return 0;
}

static std::map<std::string, std::string> parse_expected(const std::string &text) {
    std::map<std::string, std::string> kv;
    size_t pos = 0;
    while (pos < text.size()) {
        size_t nl = text.find('\n', pos);
        if (nl == std::string::npos) nl = text.size();
        std::string line = text.substr(pos, nl - pos);
        pos = nl + 1;
        if (line.empty() || line[0] == '#') continue;
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        kv[line.substr(0, eq)] = line.substr(eq + 1);
    }
    return kv;
}

int main(int argc, char **argv) {
    std::string base = argc > 1 ? argv[1] : "/tmp/hacf-r2-xhost";
    r2t::rmtree(base);
    r2t::mkdirp(base);
    const std::string fixture_dir = HACF_FIXTURE_DIR;
    const std::string expected_path = fixture_dir + "/expected.txt";
    const bool regenerate = std::getenv("ELPIS_R2_FIXTURE_REGENERATE") != nullptr;

    std::printf("R2 cross-host fixture, fixture=%s\n", fixture_dir.c_str());

    /* ---- 1. ingest the committed corpus ---------------------------------- */
    CASE("committed corpus ingests to stable identities");
    elpis_corpus *corpus = nullptr;
    CHECK(elpis_corpus_open((base + "/state").c_str(), &corpus) == 0, "corpus open");
    if (!corpus) return 1;

    for (size_t i = 0; i < sizeof kFiles / sizeof *kFiles; i++) {
        std::string body;
        CHECK(read_file(fixture_dir + "/corpus/" + kFiles[i], body) == 0,
              "cannot read fixture %s", kFiles[i]);
        elpis_ingest_meta m;
        std::memset(&m, 0, sizeof m);
        m.ns = kNs[i];
        m.authority = kAuth[i];
        m.media_type = kMedia[i];
        m.origin = kFiles[i];                      /* basename only: no build path in identity */
        elpis_ingest_result r;
        CHECK(elpis_corpus_ingest_bytes(corpus, body.data(), body.size(), &m, &r) == 0,
              "ingest %s: %s", kFiles[i], elpis_corpus_error(corpus));
    }

    char corpus_manifest_digest[65] = {0};
    char *cj = nullptr;
    CHECK(elpis_corpus_manifest_json(corpus, &cj, corpus_manifest_digest) == 0, "corpus manifest");
    if (cj) elpis_free(cj);

    /* ---- 2. enumerate chunks through the additive hook -------------------- */
    CASE("chunk enumeration is deterministic and bounded");
    std::vector<elpis_chunk_ref> refs;
    {
        const uint32_t page = 8;
        std::vector<elpis_chunk_ref> buf(page);
        uint64_t offset = 0;
        for (;;) {
            uint32_t got = 0;
            CHECK(elpis_corpus_list_chunks(corpus, nullptr, nullptr, offset, page, buf.data(), &got) == 0,
                  "list_chunks: %s", elpis_corpus_error(corpus));
            for (uint32_t i = 0; i < got; i++) refs.push_back(buf[i]);
            if (got < page) break;
            offset += got;
        }
    }
    CHECK(refs.size() >= 4, "fixture produced only %zu chunks", refs.size());
    for (size_t i = 1; i < refs.size(); i++)
        CHECK(std::strcmp(refs[i - 1].chunk_digest, refs[i].chunk_digest) < 0,
              "enumeration not sorted at %zu", i);

    /* ---- 3. embed every chunk -------------------------------------------- */
    CASE("shard build over the fixture corpus");
    elpis_embedder *emb = nullptr;
    CHECK(elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb) == 0, "embedder");
    elpis_embedding_profile profile;
    elpis_embedder_profile(emb, &profile);
    char profile_digest[65] = {0};
    elpis_embedding_profile_digest(&profile, profile_digest);

    std::vector<std::vector<float>> vecs(refs.size());
    std::vector<elpis_vshard_input> inputs;
    for (size_t i = 0; i < refs.size(); i++) {
        char *text = nullptr;
        CHECK(elpis_corpus_chunk_text(corpus, refs[i].chunk_digest, &text) == 0,
              "chunk text %zu: %s", i, elpis_corpus_error(corpus));
        vecs[i].resize(D);
        CHECK(elpis_embedder_embed(emb, text ? text : "", text ? std::strlen(text) : 0,
                                   vecs[i].data(), D) == 0, "embed %zu", i);
        if (text) elpis_free(text);
        elpis_vshard_input in;
        std::snprintf(in.chunk_digest, sizeof in.chunk_digest, "%s", refs[i].chunk_digest);
        std::snprintf(in.doc_digest, sizeof in.doc_digest, "%s", refs[i].doc_digest);
        in.ns = refs[i].ns;
        in.authority = refs[i].authority;
        in.vector = vecs[i].data();
        inputs.push_back(in);
    }

    void *shard_bytes = nullptr;
    size_t shard_len = 0;
    char shard_digest[65] = {0};
    CHECK(elpis_vshard_build(inputs.data(), inputs.size(), &profile, corpus_manifest_digest,
                             &shard_bytes, &shard_len, shard_digest) == 0, "shard build");

    /* ---- 4. admit and query ---------------------------------------------- */
    CASE("index admission and query over the fixture shard");
    fms_ctx *fms = r2t::make_fms(base + "/cold", 8ull << 20);
    CHECK(fms != nullptr, "fms");
    elpis_vector_index *ix = nullptr;
    CHECK(elpis_vector_index_create(fms, &profile, corpus_manifest_digest, &ix) == 0, "index");
    CHECK(elpis_vector_index_add_shard_bytes(ix, shard_bytes, shard_len, nullptr) == ELPIS_VEC_OK,
          "admit: %s", elpis_vector_index_error(ix));

    char index_manifest_digest[65] = {0};
    char *ij = nullptr;
    CHECK(elpis_vector_index_manifest_json(ix, &ij, index_manifest_digest) == 0, "index manifest");
    if (ij) elpis_free(ij);

    std::vector<float> qv(D);
    CHECK(elpis_embedder_embed(emb, kQuery, std::strlen(kQuery), qv.data(), D) == 0, "embed query");
    char query_digest[65] = {0};
    {
        uint8_t d[32];
        elpis_sha256(kQuery, std::strlen(kQuery), d);
        elpis_hex32(d, query_digest);
    }

    elpis_vector_query q;
    std::memset(&q, 0, sizeof q);
    q.vector = qv.data();
    q.dimensions = D;
    q.k = kTopK;
    std::vector<elpis_vector_hit> hits(kTopK);
    uint32_t n = 0;
    CHECK(elpis_vector_index_search(ix, &q, hits.data(), &n) == ELPIS_VEC_OK, "search: %s",
          elpis_vector_index_error(ix));
    CHECK(n > 0, "fixture query returned nothing");

    char result_digest[65] = {0};
    elpis_vector_result_digest(hits.data(), n, result_digest);

    /* ---- 5. compare against the committed expectations -------------------- */
    CASE("all seven identities match the committed fixture");
    std::string actual;
    actual += "# HACF R2 cross-host fixture expectations\n";
    actual += "# Regenerate only when a profile or ABI deliberately changes.\n";
    actual += std::string("embedding_profile_digest=") + profile_digest + "\n";
    actual += std::string("corpus_manifest_digest=") + corpus_manifest_digest + "\n";
    actual += std::string("shard_digest=") + shard_digest + "\n";
    actual += std::string("index_manifest_digest=") + index_manifest_digest + "\n";
    actual += std::string("query_digest=") + query_digest + "\n";
    actual += "chunk_count=" + std::to_string(refs.size()) + "\n";
    actual += "hit_count=" + std::to_string(n) + "\n";
    for (uint32_t i = 0; i < n; i++) {
        actual += "hit_" + std::to_string(i) + "=" + hits[i].chunk_digest + ":" +
                  std::to_string((long long)hits[i].score_key) + "\n";
    }
    actual += std::string("result_digest=") + result_digest + "\n";

    if (regenerate) {
        FILE *f = std::fopen(expected_path.c_str(), "wb");
        CHECK(f != nullptr, "cannot write %s", expected_path.c_str());
        if (f) { std::fwrite(actual.data(), 1, actual.size(), f); std::fclose(f); }
        std::printf("  REGENERATED %s\n%s", expected_path.c_str(), actual.c_str());
    } else {
        std::string want;
        CHECK(read_file(expected_path, want) == 0, "missing committed fixture %s",
              expected_path.c_str());
        if (!want.empty()) {
            auto we = parse_expected(want), ae = parse_expected(actual);
            for (const auto &kv : we) {
                auto it = ae.find(kv.first);
                CHECK(it != ae.end(), "expected key %s not produced", kv.first.c_str());
                if (it != ae.end())
                    CHECK(it->second == kv.second, "%s\n      expected %s\n      actual   %s",
                          kv.first.c_str(), kv.second.c_str(), it->second.c_str());
            }
            for (const auto &kv : ae)
                CHECK(we.find(kv.first) != we.end(), "unexpected key %s produced", kv.first.c_str());
        }
    }

    /* Re-running the whole pipeline in one process must be idempotent. */
    CASE("second run of the same pipeline is identical");
    {
        std::vector<elpis_vector_hit> h2(kTopK);
        uint32_t n2 = 0;
        elpis_vector_index_search(ix, &q, h2.data(), &n2);
        char d2[65];
        elpis_vector_result_digest(h2.data(), n2, d2);
        CHECK(n2 == n && std::strcmp(d2, result_digest) == 0, "repeat query digest differs");
    }

    std::free(shard_bytes);
    elpis_vector_index_destroy(ix);
    fms_destroy(fms);
    elpis_embedder_destroy(emb);
    elpis_corpus_close(corpus);

    std::printf("%d checks, %d failures\n", checks, fails);
    return fails != 0;
}
