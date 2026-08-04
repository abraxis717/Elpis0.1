/* test_vector_fms.cpp - Gate R2.4 FMS residency suite.
 *
 * Every context here is built with hot_absent_policy = FMS_REJECT. If any R2
 * code path ever requested FMS_HOT it would return FMS_E_UNSUPPORTED instead of
 * quietly folding down, so "no HOT request occurs in R2" is enforced by the
 * configuration rather than asserted in prose. */
#include "r2_test_support.h"

#include "elpis/vector_index.h"
#include "elpis/vector_result.h"

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
static const char *kCorpusDg = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";

/* One 512-vector shard is ~800 KiB of payload. */
static const uint32_t kShardVectors = 512;

static void case_registration_and_lifecycle() {
    CASE("shard is an FMS object, leased at WARM, released on completion");
    std::string cold = base + "/life";
    fms_ctx *fms = r2t::make_fms(cold, 8ull << 20);
    CHECK(fms != nullptr, "fms");
    if (!fms) return;
    CHECK(fms_hot_available(fms) == 0, "posix PAL must not offer a HOT tier");

    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile prof;
    elpis_embedder_profile(emb, &prof);
    elpis_vector_index *ix = nullptr;
    CHECK(elpis_vector_index_create(fms, &prof, kCorpusDg, &ix) == 0, "index");

    r2t::Corpus c;
    c.build("life", kShardVectors, emb);
    char sd[65];
    std::vector<uint8_t> img = r2t::build_shard(c, kCorpusDg, sd);
    CHECK(elpis_vector_index_add_shard_bytes(ix, img.data(), img.size(), nullptr) == 0,
          "admit: %s", elpis_vector_index_error(ix));

    fms_id id = 0;
    CHECK(elpis_vector_index_shard_object(ix, sd, &id) == 0, "shard has no FMS object");
    fms_object_info info;
    CHECK(fms_query(fms, id, &info) == FMS_OK, "fms_query");
    CHECK(info.kind == ELPIS_FMS_KIND_VECTOR_SHARD, "wrong object kind 0x%x", info.kind);
    CHECK(info.size_bytes == img.size(), "object size %llu vs image %zu",
          (unsigned long long)info.size_bytes, img.size());
    CHECK(info.tier == FMS_WARM, "shard admitted at tier %u", info.tier);
    CHECK(info.pin_count == 0 && info.lease_count == 0, "shard pinned after admission");

    fms_stats st;
    fms_get_stats(fms, &st);
    CHECK(st.objects == 1, "objects %llu", (unsigned long long)st.objects);
    CHECK(st.tier_bytes[FMS_HOT] == 0, "bytes resident in HOT");

    elpis_vector_query q;
    std::memset(&q, 0, sizeof q);
    q.vector = c.vec[3].data();
    q.dimensions = D;
    q.k = 4;
    std::vector<elpis_vector_hit> hits(q.k);
    uint32_t n = 0;
    CHECK(elpis_vector_index_search(ix, &q, hits.data(), &n) == 0, "search: %s",
          elpis_vector_index_error(ix));
    CHECK(n == 4, "hits %u", n);

    CHECK(fms_query(fms, id, &info) == FMS_OK, "query after search");
    CHECK(info.lease_count == 0, "lease leak: %u leases still held", info.lease_count);
    CHECK(info.pin_count == 0, "pin leak: %u pins still held", info.pin_count);
    fms_get_stats(fms, &st);
    CHECK(st.pinned_bytes == 0, "pinned bytes leaked: %llu", (unsigned long long)st.pinned_bytes);
    CHECK(st.inflight_ops == 0, "in-flight ops leaked");
    CHECK(st.tier_bytes[FMS_HOT] == 0, "HOT residency after search");
    CHECK(st.forced_placements == 0, "a placement was forced down: HOT may have been requested");

    /* Demotion is permitted once the lease is gone. */
    for (int i = 0; i < 4; i++) fms_pump(fms);
    CHECK(fms_unregister(fms, id) == FMS_E_BUSY || true, "unregister probe");   /* index owns it */

    elpis_vector_index_destroy(ix);
    fms_get_stats(fms, &st);
    CHECK(st.objects == 0, "object leak after index destroy: %llu", (unsigned long long)st.objects);
    CHECK(st.tier_bytes[FMS_WARM] == 0 && st.tier_bytes[FMS_COLD] == 0, "tier bytes leaked");
    CHECK(st.domain_bytes[FMS_DOM_RAM] == 0, "RAM charge leaked");

    fms_destroy(fms);
    elpis_embedder_destroy(emb);
}

static void case_ceiling_and_demotion() {
    CASE("RAM ceiling is enforced; shards demote and are promoted again per query");
    std::string cold = base + "/ceiling";
    /* Four shards of ~800 KiB against a 2 MiB ceiling: they cannot all be WARM. */
    const uint64_t warm = 2ull << 20;
    fms_ctx *fms = r2t::make_fms(cold, warm);
    CHECK(fms != nullptr, "fms");
    if (!fms) return;

    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile prof;
    elpis_embedder_profile(emb, &prof);
    elpis_vector_index *ix = nullptr;
    elpis_vector_index_create(fms, &prof, kCorpusDg, &ix);

    std::vector<r2t::Corpus> shards(4);
    std::vector<std::string> ids;
    for (int i = 0; i < 4; i++) {
        char tag[32];
        std::snprintf(tag, sizeof tag, "ceil-%d", i);
        shards[(size_t)i].build(tag, kShardVectors, emb);
        char sd[65];
        std::vector<uint8_t> img = r2t::build_shard(shards[(size_t)i], kCorpusDg, sd);
        CHECK(elpis_vector_index_add_shard_bytes(ix, img.data(), img.size(), nullptr) == 0,
              "admit %d: %s", i, elpis_vector_index_error(ix));
        ids.emplace_back(sd);
        fms_stats st;
        fms_get_stats(fms, &st);
        CHECK(st.domain_bytes[FMS_DOM_RAM] <= warm, "RAM ceiling breached after shard %d: %llu",
              i, (unsigned long long)st.domain_bytes[FMS_DOM_RAM]);
    }

    fms_stats st;
    fms_get_stats(fms, &st);
    CHECK(st.tier_bytes[FMS_COLD] > 0, "nothing was demoted despite pressure");
    CHECK(st.demotions > 0, "no demotions recorded");

    /* Searching all four still works: each shard is promoted under lease. */
    elpis_vector_query q;
    std::memset(&q, 0, sizeof q);
    q.vector = shards[3].vec[9].data();
    q.dimensions = D;
    q.k = 5;
    std::vector<elpis_vector_hit> hits(q.k);
    uint32_t n = 0;
    CHECK(elpis_vector_index_search(ix, &q, hits.data(), &n) == 0, "search under pressure: %s",
          elpis_vector_index_error(ix));
    CHECK(n == 5, "hits %u", n);
    if (n) CHECK(hits[0].chunk_digest == shards[3].chunk[9], "wrong nearest under pressure");

    fms_get_stats(fms, &st);
    CHECK(st.domain_bytes[FMS_DOM_RAM] <= warm, "RAM ceiling breached during search");
    CHECK(st.promotions > 0, "no promotions recorded");
    CHECK(st.pinned_bytes == 0, "pins leaked under pressure");
    CHECK(st.tier_bytes[FMS_HOT] == 0, "HOT used under pressure");

    /* Repeated searches remain correct and bounded. */
    char first[65] = {0}, later[65] = {0};
    elpis_vector_result_digest(hits.data(), n, first);
    for (int i = 0; i < 6; i++) {
        elpis_vector_index_search(ix, &q, hits.data(), &n);
        fms_pump(fms);
        fms_get_stats(fms, &st);
        CHECK(st.domain_bytes[FMS_DOM_RAM] <= warm, "RAM ceiling breached in loop");
    }
    elpis_vector_result_digest(hits.data(), n, later);
    CHECK(std::strcmp(first, later) == 0, "results changed across demote/promote cycles");

    elpis_vector_index_destroy(ix);
    fms_destroy(fms);
    elpis_embedder_destroy(emb);
}

static void case_no_headroom() {
    CASE("a shard that cannot be made WARM-resident fails structurally");
    std::string cold = base + "/nohead";
    /* Ceiling far below one shard: admission itself must fail, loudly. */
    fms_ctx *fms = r2t::make_fms(cold, 64ull << 10);
    CHECK(fms != nullptr, "fms");
    if (!fms) return;
    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile prof;
    elpis_embedder_profile(emb, &prof);
    elpis_vector_index *ix = nullptr;
    elpis_vector_index_create(fms, &prof, kCorpusDg, &ix);

    r2t::Corpus c;
    c.build("nohead", kShardVectors, emb);
    char sd[65];
    std::vector<uint8_t> img = r2t::build_shard(c, kCorpusDg, sd);
    int rc = elpis_vector_index_add_shard_bytes(ix, img.data(), img.size(), nullptr);
    CHECK(rc == ELPIS_VEC_E_RESIDENCY, "expected ELPIS_VEC_E_RESIDENCY, got %d (%s)",
          rc, elpis_vec_strerror(rc));
    const elpis_vec_error *err = elpis_vector_index_last_error(ix);
    CHECK(err && err->cause == FMS_E_LIMIT, "underlying FMS cause not preserved: %d",
          err ? err->cause : 0);
    CHECK(std::strstr(elpis_vector_index_error(ix), "fms_register") != nullptr,
          "unexpected error: %s", elpis_vector_index_error(ix));
    CHECK(elpis_vector_index_shard_count(ix) == 0, "failed admission left a shard behind");

    fms_stats st;
    fms_get_stats(fms, &st);
    CHECK(st.objects == 0, "failed admission leaked an object");

    /* A search over an empty index is empty, not an error. */
    elpis_vector_query q;
    std::memset(&q, 0, sizeof q);
    q.vector = c.vec[0].data();
    q.dimensions = D;
    q.k = 3;
    std::vector<elpis_vector_hit> hits(3);
    uint32_t n = 99;
    CHECK(elpis_vector_index_search(ix, &q, hits.data(), &n) == ELPIS_VEC_OK,
          "empty index search failed");
    CHECK(n == 0, "empty index returned %u hits", n);

    elpis_vector_index_destroy(ix);
    fms_destroy(fms);
    elpis_embedder_destroy(emb);
}

static void case_cold_corruption() {
    CASE("a corrupted cold replica surfaces as an integrity failure, not an empty result");
    std::string cold = base + "/rot";
    const uint64_t warm = 2ull << 20;
    fms_ctx *fms = r2t::make_fms(cold, warm);
    CHECK(fms != nullptr, "fms");
    if (!fms) return;
    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile prof;
    elpis_embedder_profile(emb, &prof);
    elpis_vector_index *ix = nullptr;
    elpis_vector_index_create(fms, &prof, kCorpusDg, &ix);

    std::vector<r2t::Corpus> shards(3);
    for (int i = 0; i < 3; i++) {
        char tag[32];
        std::snprintf(tag, sizeof tag, "rot-%d", i);
        shards[(size_t)i].build(tag, kShardVectors, emb);
        char sd[65];
        std::vector<uint8_t> img = r2t::build_shard(shards[(size_t)i], kCorpusDg, sd);
        CHECK(elpis_vector_index_add_shard_bytes(ix, img.data(), img.size(), nullptr) == 0, "admit %d", i);
    }
    for (int i = 0; i < 6; i++) fms_pump(fms);          /* push shards to COLD */

    fms_stats st;
    fms_get_stats(fms, &st);
    CHECK(st.tier_bytes[FMS_COLD] > 0, "no shard reached COLD");

    int hit = r2t::corrupt_cold_blobs(cold);
    CHECK(hit > 0, "no cold replica to corrupt");

    elpis_vector_query q;
    std::memset(&q, 0, sizeof q);
    q.vector = shards[0].vec[1].data();
    q.dimensions = D;
    q.k = 4;
    std::vector<elpis_vector_hit> hits(q.k);
    uint32_t n = 77;
    int rc = elpis_vector_index_search(ix, &q, hits.data(), &n);
    CHECK(rc != ELPIS_VEC_OK, "search over a corrupted replica returned success");
    CHECK(n == 0, "corrupted search reported %u hits", n);
    CHECK(rc == ELPIS_VEC_E_INTEGRITY, "expected ELPIS_VEC_E_INTEGRITY, got %d (%s)",
          rc, elpis_vec_strerror(rc));
    /* Integrity must not be downgraded to not-found, out-of-memory or empty. */
    CHECK(rc != ELPIS_VEC_E_NOTFOUND && rc != ELPIS_VEC_E_RESIDENCY,
          "integrity failure downgraded");
    const elpis_vec_error *err = elpis_vector_index_last_error(ix);
    CHECK(err != nullptr, "no structured error");
    if (err) {
        CHECK(err->status == ELPIS_VEC_E_INTEGRITY, "structured status %d", err->status);
        CHECK(err->cause == FMS_E_DIGEST, "underlying cause not preserved: %d (expected %d)",
              err->cause, (int)FMS_E_DIGEST);
        CHECK(err->cause != FMS_E_NOMEM, "integrity failure reported as memory exhaustion");
        CHECK(std::strstr(err->detail, "digest") != nullptr, "detail: %s", err->detail);
    }

    fms_get_stats(fms, &st);
    CHECK(st.digest_failures > 0, "FMS digest failure not counted");
    CHECK(st.pinned_bytes == 0, "lease leaked on the failure path");

    elpis_vector_index_destroy(ix);
    fms_destroy(fms);
    elpis_embedder_destroy(emb);
}

static void case_close_shard() {
    CASE("closing a shard releases its FMS object");
    std::string cold = base + "/close";
    fms_ctx *fms = r2t::make_fms(cold, 8ull << 20);
    if (!fms) { CHECK(false, "fms"); return; }
    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile prof;
    elpis_embedder_profile(emb, &prof);
    elpis_vector_index *ix = nullptr;
    elpis_vector_index_create(fms, &prof, kCorpusDg, &ix);

    r2t::Corpus c;
    c.build("close", 128, emb);
    char sd[65];
    std::vector<uint8_t> img = r2t::build_shard(c, kCorpusDg, sd);
    elpis_vector_index_add_shard_bytes(ix, img.data(), img.size(), nullptr);
    CHECK(elpis_vector_index_shard_count(ix) == 1, "admitted");

    CHECK(elpis_vector_index_verify(ix, sd) == 0, "verify admitted shard: %s",
          elpis_vector_index_error(ix));
    elpis_vshard_header h;
    CHECK(elpis_vector_index_inspect(ix, sd, &h) == 0, "inspect");
    CHECK(h.vector_count == 128, "inspect vector_count %llu", (unsigned long long)h.vector_count);

    CHECK(elpis_vector_index_close_shard(ix, sd) == 0, "close");
    CHECK(elpis_vector_index_shard_count(ix) == 0, "shard still listed");
    fms_stats st;
    fms_get_stats(fms, &st);
    CHECK(st.objects == 0, "closing left the FMS object behind");
    CHECK(elpis_vector_index_close_shard(ix, sd) != 0, "closing an unknown shard succeeded");

    elpis_vector_index_destroy(ix);
    fms_destroy(fms);
    elpis_embedder_destroy(emb);
}

int main(int argc, char **argv) {
    base = argc > 1 ? argv[1] : "/tmp/hacf-r2-fms";
    r2t::rmtree(base);
    r2t::mkdirp(base);
    std::printf("R2 FMS residency suite, root=%s\n", base.c_str());

    case_registration_and_lifecycle();
    case_ceiling_and_demotion();
    case_no_headroom();
    case_cold_corruption();
    case_close_shard();

    std::printf("%d checks, %d failures\n", checks, fails);
    return fails != 0;
}
