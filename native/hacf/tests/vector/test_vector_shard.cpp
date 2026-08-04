/* test_vector_shard.cpp - Gate R2.2 shard format suite.
 * Every rejection listed in the R2 shard-format contract has a case here. */
#include "elpis/vector_shard.h"
#include "elpis/embedding_provider.h"
#include "elpis/sha256.h"

#include <sys/stat.h>
#include <unistd.h>

#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdlib>
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

/* Header field offsets, mirrored from the format contract so the test would
 * catch an accidental layout change in the writer. */
enum : size_t {
    OFF_MAGIC = 0, OFF_ABI = 8, OFF_HEADER_BYTES = 12, OFF_VCOUNT = 16, OFF_DIM = 24,
    OFF_ELEM = 28, OFF_METRIC = 32, OFF_NORM = 36, OFF_RECBYTES = 40,
    OFF_PAYLOAD_LEN = 48, OFF_META_LEN = 56, OFF_HEADER_DG = 192
};

static void put_u32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}
static void put_u64(uint8_t *p, uint64_t v) { for (int i = 0; i < 8; i++) p[i] = (uint8_t)(v >> (8 * i)); }

/* Recompute the header digest so a mutation reaches the check it targets
 * instead of stopping at header_digest_mismatch. */
static void reseal_header(std::vector<uint8_t> &img) {
    std::memset(img.data() + OFF_HEADER_DG, 0, 32);
    uint8_t d[32];
    elpis_sha256(img.data(), ELPIS_VSHARD_HEADER_BYTES, d);
    std::memcpy(img.data() + OFF_HEADER_DG, d, 32);
}

struct Fixture {
    elpis_embedding_profile profile{};
    std::vector<std::string> chunk_hex, doc_hex;
    std::vector<std::vector<float>> vecs;
    std::vector<elpis_vshard_input> inputs;
};

static Fixture make_fixture(uint32_t n, const char *tag = "doc") {
    Fixture f;
    elpis_embedder *e = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &e);
    elpis_embedder_profile(e, &f.profile);
    for (uint32_t i = 0; i < n; i++) {
        char seed[128];
        std::snprintf(seed, sizeof seed, "%s-chunk-%u", tag, i);
        uint8_t d[32];
        char hex[65];
        elpis_sha256(seed, std::strlen(seed), d);
        elpis_hex32(d, hex);
        f.chunk_hex.emplace_back(hex);
        std::snprintf(seed, sizeof seed, "%s-document", tag);
        elpis_sha256(seed, std::strlen(seed), d);
        elpis_hex32(d, hex);
        f.doc_hex.emplace_back(hex);
        std::vector<float> v(D);
        std::snprintf(seed, sizeof seed, "%s-body-%u", tag, i);
        elpis_embedder_embed(e, seed, std::strlen(seed), v.data(), D);
        f.vecs.push_back(std::move(v));
    }
    for (uint32_t i = 0; i < n; i++) {
        elpis_vshard_input in;
        std::snprintf(in.chunk_digest, sizeof in.chunk_digest, "%s", f.chunk_hex[i].c_str());
        std::snprintf(in.doc_digest, sizeof in.doc_digest, "%s", f.doc_hex[i].c_str());
        in.ns = (i % 2) ? "elpis.docs" : "elpis.code";
        in.authority = (i % 3) ? "reference" : "canonical";
        in.vector = f.vecs[i].data();
        f.inputs.push_back(in);
    }
    elpis_embedder_destroy(e);
    return f;
}

static const char *kCorpusDg = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";

static std::vector<uint8_t> build_ok(const Fixture &f, char digest_out[65]) {
    void *b = nullptr;
    size_t n = 0;
    if (elpis_vshard_build(f.inputs.data(), f.inputs.size(), &f.profile, kCorpusDg, &b, &n,
                           digest_out) != 0)
        return {};
    std::vector<uint8_t> v((uint8_t *)b, (uint8_t *)b + n);
    std::free(b);
    return v;
}

static void expect_reject(std::vector<uint8_t> img, const char *want, const char *label) {
    char reason[64] = {0};
    int rc = elpis_vshard_verify(img.data(), img.size(), nullptr, reason, sizeof reason);
    CHECK(rc != 0, "%s was accepted", label);
    if (rc != 0)
        CHECK(std::strcmp(reason, want) == 0, "%s gave reason '%s', expected '%s'", label, reason, want);
}

/* ------------------------------------------------------------------ cases -- */

static void case_roundtrip() {
    CASE("byte-identical build and clean round trip");
    Fixture f = make_fixture(16);
    char d1[65], d2[65];
    std::vector<uint8_t> a = build_ok(f, d1);
    CHECK(!a.empty(), "build");
    if (a.empty()) return;

    /* Same logical content, shuffled input order, must give identical bytes. */
    Fixture g = f;
    std::vector<elpis_vshard_input> rev(g.inputs.rbegin(), g.inputs.rend());
    g.inputs = rev;
    std::vector<uint8_t> b = build_ok(g, d2);
    CHECK(a.size() == b.size() && std::memcmp(a.data(), b.data(), a.size()) == 0,
          "shard bytes depend on input order");
    CHECK(std::strcmp(d1, d2) == 0, "shard digest depends on input order");

    elpis_vshard_header h;
    char reason[64] = {0};
    CHECK(elpis_vshard_verify(a.data(), a.size(), &h, reason, sizeof reason) == 0,
          "clean shard rejected: %s", reason);
    CHECK(h.vector_count == 16, "vector_count %llu", (unsigned long long)h.vector_count);
    CHECK(h.dimensions == D, "dimensions %u", h.dimensions);
    CHECK(h.record_bytes == ELPIS_VSHARD_RECORD_BYTES, "record_bytes %u", h.record_bytes);
    CHECK(std::strcmp(h.corpus_manifest_digest, kCorpusDg) == 0, "corpus digest not bound");
    CHECK(std::strcmp(h.shard_digest, d1) == 0, "shard digest mismatch");
    CHECK(a.size() == ELPIS_VSHARD_HEADER_BYTES + h.payload_bytes + h.metadata_bytes,
          "declared sizes do not cover the image");

    /* Records are sorted by chunk digest and readable. */
    for (uint64_t i = 1; i < h.vector_count; i++) {
        char p[65], q[65];
        elpis_vshard_record_chunk_hex(a.data(), i - 1, p);
        elpis_vshard_record_chunk_hex(a.data(), i, q);
        CHECK(std::strcmp(p, q) < 0, "records not sorted at %llu", (unsigned long long)i);
    }
    /* Vector round trip is exact. */
    for (uint64_t i = 0; i < h.vector_count; i++) {
        char hex[65];
        elpis_vshard_record_chunk_hex(a.data(), i, hex);
        size_t src = 0;
        while (src < f.inputs.size() && std::strcmp(f.inputs[src].chunk_digest, hex) != 0) src++;
        CHECK(src < f.inputs.size(), "record %llu not found in input", (unsigned long long)i);
        if (src < f.inputs.size()) {
            const float *v = elpis_vshard_record_vector(a.data(), i);
            CHECK(std::memcmp(v, f.inputs[src].vector, D * sizeof(float)) == 0,
                  "vector %llu altered by the round trip", (unsigned long long)i);
        }
    }
    /* Metadata side table survives. */
    const char *ns = nullptr, *au = nullptr;
    CHECK(elpis_vshard_record_meta(a.data(), a.size(), 0, &ns, &au) == 0, "meta lookup");
    CHECK(ns && au && *ns && *au, "empty metadata");
}

static void case_file_io() {
    CASE("shard files are immutable on disk");
    Fixture f = make_fixture(4);
    char dg[65];
    std::vector<uint8_t> img = build_ok(f, dg);
    std::string path = base + "/shard-a.vshard";
    CHECK(elpis_vshard_write(path.c_str(), img.data(), img.size()) == 0, "write");
    CHECK(elpis_vshard_write(path.c_str(), img.data(), img.size()) != 0, "overwrite was allowed");

    void *rb = nullptr;
    size_t rn = 0;
    CHECK(elpis_vshard_read_file(path.c_str(), &rb, &rn) == 0, "read back");
    CHECK(rn == img.size() && std::memcmp(rb, img.data(), rn) == 0, "file differs from memory image");
    char reason[64] = {0};
    CHECK(elpis_vshard_verify(rb, rn, nullptr, reason, sizeof reason) == 0, "file failed verify: %s", reason);
    std::free(rb);
}

static void case_rejections() {
    CASE("every corruption class is rejected");
    Fixture f = make_fixture(8);
    char dg[65];
    std::vector<uint8_t> ok = build_ok(f, dg);
    CHECK(!ok.empty(), "build");
    if (ok.empty()) return;

    { auto v = ok; v[0] = 'X'; expect_reject(v, "bad_magic", "wrong magic"); }
    { auto v = ok; put_u32(v.data() + OFF_ABI, 99); reseal_header(v);
      expect_reject(v, "unsupported_abi", "wrong ABI"); }
    { auto v = ok; put_u32(v.data() + OFF_HEADER_BYTES, 512); reseal_header(v);
      expect_reject(v, "bad_header_bytes", "wrong header size"); }
    { auto v = ok; put_u32(v.data() + OFF_DIM, 512); reseal_header(v);
      expect_reject(v, "bad_dimensions", "wrong dimensions"); }
    { auto v = ok; put_u32(v.data() + OFF_ELEM, 42); reseal_header(v);
      expect_reject(v, "unknown_element_type", "unknown element type"); }
    { auto v = ok; put_u32(v.data() + OFF_METRIC, 42); reseal_header(v);
      expect_reject(v, "unknown_metric", "unknown metric"); }
    { auto v = ok; put_u32(v.data() + OFF_NORM, 42); reseal_header(v);
      expect_reject(v, "unknown_normalization", "unknown normalization"); }
    { auto v = ok; put_u32(v.data() + OFF_RECBYTES, 64); reseal_header(v);
      expect_reject(v, "bad_record_bytes", "wrong record size"); }
    { auto v = ok; v.resize(ELPIS_VSHARD_HEADER_BYTES - 1);
      expect_reject(v, "truncated_header", "truncated header"); }
    { auto v = ok; v.resize(v.size() - 64);
      expect_reject(v, "truncated_payload", "truncated payload"); }
    { auto v = ok; v.resize(v.size() + 32, 0);
      expect_reject(v, "extra_undeclared_payload", "trailing garbage"); }
    { auto v = ok; put_u64(v.data() + OFF_PAYLOAD_LEN, 12345); reseal_header(v);
      expect_reject(v, "payload_size_mismatch", "payload size mismatch"); }
    { auto v = ok; put_u64(v.data() + OFF_VCOUNT, 0); reseal_header(v);
      expect_reject(v, "bad_vector_count", "zero vector count"); }
    { auto v = ok; put_u64(v.data() + OFF_VCOUNT, 0xFFFFFFFFFFFFFFF0ull); reseal_header(v);
      expect_reject(v, "bad_vector_count", "absurd vector count"); }
    { auto v = ok; put_u64(v.data() + OFF_VCOUNT, (UINT64_MAX / ELPIS_VSHARD_RECORD_BYTES) + 2);
      reseal_header(v); expect_reject(v, "bad_vector_count", "overflowing vector count"); }
    { auto v = ok; v[ELPIS_VSHARD_HEADER_BYTES + 100] ^= 0xFF;
      expect_reject(v, "payload_digest_mismatch", "payload corruption"); }
    { auto v = ok; v[v.size() - 1] ^= 0xFF;
      expect_reject(v, "metadata_map_digest_mismatch", "metadata corruption"); }
    { auto v = ok; v[OFF_HEADER_DG + 3] ^= 0xFF;
      expect_reject(v, "header_digest_mismatch", "header corruption"); }

    /* Non-finite stored value: patch a float, then re-seal payload and header
     * so the value check is the one that fires. */
    {
        auto v = ok;
        uint32_t inf_bits = 0x7F800000u;
        put_u32(v.data() + ELPIS_VSHARD_HEADER_BYTES + 64, inf_bits);
        uint64_t paylen = 0;
        for (int i = 0; i < 8; i++) paylen |= (uint64_t)v[OFF_PAYLOAD_LEN + i] << (8 * i);
        uint8_t d[32];
        elpis_sha256(v.data() + ELPIS_VSHARD_HEADER_BYTES, (size_t)paylen, d);
        std::memcpy(v.data() + 160, d, 32);
        reseal_header(v);
        expect_reject(v, "non_finite_vector", "infinity in a stored vector");
    }

    /* Duplicate chunk digests are refused by the builder itself. */
    {
        Fixture d = make_fixture(4);
        std::snprintf(d.inputs[2].chunk_digest, sizeof d.inputs[2].chunk_digest, "%s",
                      d.inputs[1].chunk_digest);
        void *b = nullptr;
        size_t n = 0;
        char dg2[65];
        CHECK(elpis_vshard_build(d.inputs.data(), d.inputs.size(), &d.profile, kCorpusDg, &b, &n, dg2) != 0,
              "builder accepted duplicate chunk digests");
        if (b) std::free(b);
    }
    /* And by the reader, if a hand-crafted image contains them. */
    {
        auto v = ok;
        std::memcpy(v.data() + ELPIS_VSHARD_HEADER_BYTES + ELPIS_VSHARD_RECORD_BYTES,
                    v.data() + ELPIS_VSHARD_HEADER_BYTES, 32);
        uint64_t paylen = 0;
        for (int i = 0; i < 8; i++) paylen |= (uint64_t)v[OFF_PAYLOAD_LEN + i] << (8 * i);
        uint8_t d[32];
        elpis_sha256(v.data() + ELPIS_VSHARD_HEADER_BYTES, (size_t)paylen, d);
        std::memcpy(v.data() + 160, d, 32);
        reseal_header(v);
        expect_reject(v, "duplicate_chunk_digest", "duplicate chunk digest in the payload");
    }
}

static void case_builder_input_validation() {
    CASE("builder rejects malformed input before allocating an image");
    Fixture f = make_fixture(4);
    void *b = nullptr;
    size_t n = 0;
    char dg[65];

    { auto g = f; std::snprintf(g.inputs[0].chunk_digest, 65, "short");
      CHECK(elpis_vshard_build(g.inputs.data(), g.inputs.size(), &g.profile, kCorpusDg, &b, &n, dg) != 0,
            "invalid chunk digest accepted"); }
    { auto g = f; std::snprintf(g.inputs[1].doc_digest, 65, "zz%062d", 0);
      CHECK(elpis_vshard_build(g.inputs.data(), g.inputs.size(), &g.profile, kCorpusDg, &b, &n, dg) != 0,
            "invalid document digest accepted"); }
    { auto g = f; std::vector<float> bad(D, 0.0f); bad[3] = std::nanf(""); g.inputs[2].vector = bad.data();
      CHECK(elpis_vshard_build(g.inputs.data(), g.inputs.size(), &g.profile, kCorpusDg, &b, &n, dg) != 0,
            "NaN vector accepted"); }
    { auto g = f; g.profile.dimensions = 128;
      CHECK(elpis_vshard_build(g.inputs.data(), g.inputs.size(), &g.profile, kCorpusDg, &b, &n, dg) != 0,
            "wrong profile dimension accepted"); }
    { auto g = f;
      CHECK(elpis_vshard_build(g.inputs.data(), 0, &g.profile, kCorpusDg, &b, &n, dg) != 0,
            "empty shard accepted"); }
    { auto g = f;
      CHECK(elpis_vshard_build(g.inputs.data(), g.inputs.size(), &g.profile, "not-a-digest", &b, &n, dg) != 0,
            "invalid corpus digest accepted"); }
}

static void case_manifest() {
    CASE("shard manifest is canonical and stable");
    Fixture f = make_fixture(6);
    char dg[65];
    std::vector<uint8_t> img = build_ok(f, dg);
    elpis_vshard_header h;
    elpis_vshard_verify(img.data(), img.size(), &h, nullptr, 0);

    char *j1 = nullptr, *j2 = nullptr;
    char m1[65], m2[65];
    CHECK(elpis_vshard_manifest_json(&h, &j1, m1) == 0, "manifest");
    CHECK(elpis_vshard_manifest_json(&h, &j2, m2) == 0, "manifest again");
    CHECK(j1 && j2 && std::strcmp(j1, j2) == 0, "manifest not byte-stable");
    CHECK(std::strcmp(m1, m2) == 0, "manifest digest not stable");
    CHECK(std::strstr(j1, "\"abi_version\":") == j1 + 1, "keys not in canonical order");
    CHECK(std::strstr(j1, "nan") == nullptr && std::strstr(j1, "Inf") == nullptr,
          "manifest contains a non-finite literal");
    CHECK(std::strchr(j1, '.') == nullptr,
          "manifest contains a decimal point: floating point leaked into an identity");
    std::free(j1);
    std::free(j2);
}

int main(int argc, char **argv) {
    base = argc > 1 ? argv[1] : "/tmp/hacf-r2-shard";
    mkdir(base.c_str(), 0700);
    /* Start from a clean directory so the immutability check is meaningful. */
    std::string a = base + "/shard-a.vshard";
    unlink(a.c_str());
    std::printf("R2 shard format suite, dir=%s\n", base.c_str());

    case_roundtrip();
    case_file_io();
    case_rejections();
    case_builder_input_validation();
    case_manifest();

    std::printf("%d checks, %d failures\n", checks, fails);
    return fails != 0;
}
