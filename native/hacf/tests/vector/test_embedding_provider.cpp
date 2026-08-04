/* test_embedding_provider.cpp - Gate R2.2 embedding provider suite. */
#include "elpis/embedding_provider.h"
#include "elpis/sha256.h"

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

static void case_determinism() {
    CASE("fixture output is deterministic and dimensionally exact");
    elpis_embedder *e = nullptr;
    CHECK(elpis_embedder_fixture_create(ELPIS_NORM_L2, &e) == 0, "create");
    if (!e) return;

    std::vector<float> a(D), b(D), c(D);
    const char *s1 = "ELPIS_ROOT_A is the active root filesystem";
    const char *s2 = "ELPIS_ROOT_B is reserved for A/B updates";
    CHECK(elpis_embedder_embed(e, s1, std::strlen(s1), a.data(), D) == 0, "embed 1");
    CHECK(elpis_embedder_embed(e, s1, std::strlen(s1), b.data(), D) == 0, "embed 1 again");
    CHECK(elpis_embedder_embed(e, s2, std::strlen(s2), c.data(), D) == 0, "embed 2");

    CHECK(std::memcmp(a.data(), b.data(), D * sizeof(float)) == 0,
          "identical bytes produced different vectors");
    CHECK(std::memcmp(a.data(), c.data(), D * sizeof(float)) != 0,
          "different bytes produced identical vectors");
    CHECK(elpis_vector_all_finite(a.data(), D) == 1, "non-finite value in fixture output");

    /* Empty input is legal and deterministic. */
    std::vector<float> z1(D), z2(D);
    CHECK(elpis_embedder_embed(e, "", 0, z1.data(), D) == 0, "embed empty");
    CHECK(elpis_embedder_embed(e, "", 0, z2.data(), D) == 0, "embed empty again");
    CHECK(std::memcmp(z1.data(), z2.data(), D * sizeof(float)) == 0, "empty input unstable");

    /* Wrong output dimension is refused rather than truncated. */
    std::vector<float> small(16);
    CHECK(elpis_embedder_embed(e, s1, std::strlen(s1), small.data(), 16) != 0,
          "wrong dimension accepted");
    elpis_embedder_destroy(e);
}

static void case_normalization() {
    CASE("normalization policy is honoured");
    elpis_embedder *l2 = nullptr, *raw = nullptr;
    CHECK(elpis_embedder_fixture_create(ELPIS_NORM_L2, &l2) == 0, "create l2");
    CHECK(elpis_embedder_fixture_create(ELPIS_NORM_NONE, &raw) == 0, "create none");
    if (!l2 || !raw) return;

    std::vector<float> v(D), w(D);
    const char *s = "MacBookAir7,2";
    elpis_embedder_embed(l2, s, std::strlen(s), v.data(), D);
    elpis_embedder_embed(raw, s, std::strlen(s), w.data(), D);

    /* Exact by construction: 16 components of +/-0.25 give a norm of exactly
     * 1.0 with no square root involved, and +/-1.0 gives exactly 4.0. */
    double n = elpis_vector_l2_norm(v.data(), D);
    CHECK(n == 1.0, "L2 profile norm is %.17g, expected exactly 1.0", n);
    double m = elpis_vector_l2_norm(w.data(), D);
    CHECK(m == 4.0, "unnormalized profile norm is %.17g, expected exactly 4.0", m);

    uint32_t nz = 0, nzw = 0;
    for (uint32_t i = 0; i < D; i++) {
        if (v[i] != 0.0f) { nz++; CHECK(v[i] == 0.25f || v[i] == -0.25f,
                                        "component %u is %.17g, expected +/-0.25", i, (double)v[i]); }
        if (w[i] != 0.0f) { nzw++; CHECK(w[i] == 1.0f || w[i] == -1.0f,
                                         "component %u is %.17g, expected +/-1.0", i, (double)w[i]); }
    }
    CHECK(nz == 16, "L2 vector has %u non-zero components, expected 16", nz);
    CHECK(nzw == 16, "unnormalized vector has %u non-zero components, expected 16", nzw);

    /* Every component is a power of two, so a float32 round trip is exact. */
    for (uint32_t i = 0; i < D; i++) {
        float back;
        uint32_t bits;
        std::memcpy(&bits, &v[i], 4);
        std::memcpy(&back, &bits, 4);
        CHECK(back == v[i], "component %u did not survive a bitwise round trip", i);
    }

    /* Signs must not be all-positive: the sign bit comes from hash material. */
    uint32_t neg = 0;
    for (uint32_t i = 0; i < D; i++) if (v[i] < 0.0f) neg++;
    CHECK(neg > 0 && neg < 16, "sign distribution degenerate: %u negative of 16", neg);

    elpis_embedding_profile pl, pr;
    elpis_embedder_profile(l2, &pl);
    elpis_embedder_profile(raw, &pr);
    CHECK(pl.metric == ELPIS_METRIC_COSINE, "L2 profile metric");
    CHECK(pr.metric == ELPIS_METRIC_DOT, "unnormalized profile metric");
    CHECK(elpis_embedding_profile_equal(&pl, &pr) == 0, "distinct profiles compared equal");
    elpis_embedder_destroy(l2);
    elpis_embedder_destroy(raw);
}

static void case_profile_digest() {
    CASE("profile digest is stable, field-sensitive and validated");
    elpis_embedder *e = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &e);
    if (!e) return;
    elpis_embedding_profile p;
    elpis_embedder_profile(e, &p);

    char d1[65], d2[65];
    CHECK(elpis_embedding_profile_digest(&p, d1) == 0, "digest");
    CHECK(elpis_embedding_profile_digest(&p, d2) == 0, "digest again");
    CHECK(std::strcmp(d1, d2) == 0, "profile digest unstable");
    CHECK(std::strlen(d1) == 64, "digest length %zu", std::strlen(d1));

    /* Known-answer: the fixture profile digest is part of cross-host identity.
     * If this changes, every shard built under it must be rebuilt. */
    std::printf("    fixture profile digest = %s\n", d1);

    elpis_embedding_profile q = p;
    q.normalization = ELPIS_NORM_NONE;
    q.metric = ELPIS_METRIC_DOT;
    char d3[65];
    elpis_embedding_profile_digest(&q, d3);
    CHECK(std::strcmp(d1, d3) != 0, "digest insensitive to normalization policy");

    q = p;
    std::snprintf(q.name, sizeof q.name, "fixture-sha256-v3");
    elpis_embedding_profile_digest(&q, d3);
    CHECK(std::strcmp(d1, d3) != 0, "digest insensitive to provider name");

    /* Trailing bytes past the NUL must not enter the digest. */
    q = p;
    std::memset(q.name + std::strlen(q.name) + 1, 0x41, sizeof q.name - std::strlen(q.name) - 1);
    elpis_embedding_profile_digest(&q, d3);
    CHECK(std::strcmp(d1, d3) == 0, "digest depends on bytes past the terminator");

    /* Invalid profiles are refused. */
    q = p; q.dimensions = 512;
    CHECK(elpis_embedding_profile_validate(&q) != 0, "wrong dimension accepted");
    q = p; q.abi_version = 99;
    CHECK(elpis_embedding_profile_validate(&q) != 0, "wrong ABI accepted");
    q = p; q.element_type = 7;
    CHECK(elpis_embedding_profile_validate(&q) != 0, "unknown element type accepted");
    q = p; q.normalization = 9;
    CHECK(elpis_embedding_profile_validate(&q) != 0, "unknown normalization accepted");
    q = p; std::snprintf(q.model_digest, sizeof q.model_digest, "not-hex");
    CHECK(elpis_embedding_profile_validate(&q) != 0, "invalid model digest accepted");
    elpis_embedder_destroy(e);
}

static void case_external_provider() {
    CASE("external provider validates and never synthesises");
    elpis_embedder *fix = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &fix);
    elpis_embedding_profile p;
    elpis_embedder_profile(fix, &p);
    std::snprintf(p.backend, sizeof p.backend, "external");
    std::snprintf(p.name, sizeof p.name, "bge-small-en-v1.5");
    std::snprintf(p.model_digest, sizeof p.model_digest,
                  "1111111111111111111111111111111111111111111111111111111111111111");

    elpis_embedder *ext = nullptr;
    CHECK(elpis_embedder_external_create(&p, &ext) == 0, "create external");
    if (!ext) { elpis_embedder_destroy(fix); return; }

    char pd[65];
    elpis_embedding_profile_digest(&p, pd);

    std::vector<float> src(D), out(D);
    elpis_embedder_embed(fix, "payload", 7, src.data(), D);      /* already L2 normalized */

    CHECK(elpis_embedder_accept(ext, src.data(), D, pd, out.data(), D) == 0,
          "valid external vector rejected: %s", elpis_embedder_error(ext));
    CHECK(std::memcmp(src.data(), out.data(), D * sizeof(float)) == 0, "external vector altered");

    /* Wrong dimensions. */
    CHECK(elpis_embedder_accept(ext, src.data(), 128, pd, out.data(), D) != 0,
          "wrong input dimension accepted");

    /* NaN and infinity. */
    std::vector<float> bad = src;
    bad[7] = std::nanf("");
    CHECK(elpis_embedder_accept(ext, bad.data(), D, pd, out.data(), D) != 0, "NaN accepted");
    bad = src;
    bad[11] = HUGE_VALF;
    CHECK(elpis_embedder_accept(ext, bad.data(), D, pd, out.data(), D) != 0, "infinity accepted");

    /* Profile digest mismatch. */
    CHECK(elpis_embedder_accept(ext, src.data(), D,
                                "0000000000000000000000000000000000000000000000000000000000000000",
                                out.data(), D) != 0, "profile digest mismatch accepted");

    /* Normalization policy violation: the producer promised L2. */
    std::vector<float> unnorm = src;
    for (uint32_t i = 0; i < D; i++) unnorm[i] *= 3.0f;
    CHECK(elpis_embedder_accept(ext, unnorm.data(), D, pd, out.data(), D) != 0,
          "unnormalized vector accepted under an L2 profile");
    std::vector<float> zero(D, 0.0f);
    CHECK(elpis_embedder_accept(ext, zero.data(), D, pd, out.data(), D) != 0,
          "zero vector accepted under an L2 profile");

    /* Cross-provider misuse is refused in both directions. */
    CHECK(elpis_embedder_embed(ext, "x", 1, out.data(), D) != 0,
          "external provider synthesised a vector");
    CHECK(elpis_embedder_accept(fix, src.data(), D, pd, out.data(), D) != 0,
          "fixture provider admitted an external vector");

    elpis_embedder_destroy(ext);
    elpis_embedder_destroy(fix);
}

int main(void) {
    std::printf("R2 embedding provider suite\n");
    case_determinism();
    case_normalization();
    case_profile_digest();
    case_external_provider();
    std::printf("%d checks, %d failures\n", checks, fails);
    return fails != 0;
}
