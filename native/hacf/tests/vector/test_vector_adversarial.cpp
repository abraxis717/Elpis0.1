/* test_vector_adversarial.cpp - Remediation 01/02 regression suite.
 *
 * One case per confirmed audit finding, plus the hardening requirements. Each
 * case is written to fail on the pre-remediation code. */
#include "r2_test_support.h"

#include "elpis/corpus.h"
#include "elpis/chunking.h"
#include "elpis/vector_index.h"
#include "elpis/vector_result.h"

#include <sys/stat.h>
#include <unistd.h>

#include <atomic>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <limits>
#include <new>
#include <string>
#include <thread>
#include <vector>

/* Controlled allocation failure for C-ABI containment tests. The switch is
 * armed only immediately around the call under test; normal test setup is
 * unaffected. */
static std::atomic<int> g_fail_next_new{0};

#if defined(__GNUC__) || defined(__clang__)
#define ELPIS_TEST_NOINLINE __attribute__((noinline))
#else
#define ELPIS_TEST_NOINLINE
#endif

/* Keep the malloc/free implementation behind non-inlined helpers. GCC 16's
 * interprocedural -Wmismatched-new-delete analysis otherwise diagnoses the
 * intentional replacement new/delete pair as though ordinary malloc/free
 * were mixed at the call site. The replacement operators remain matched and
 * the allocation-failure injection semantics are unchanged. */
ELPIS_TEST_NOINLINE static void *test_raw_allocate(std::size_t n) noexcept {
    return std::malloc(n ? n : 1);
}

ELPIS_TEST_NOINLINE static void test_raw_deallocate(void *p) noexcept {
    std::free(p);
}

void *operator new(std::size_t n) {
    if (g_fail_next_new.exchange(0) != 0) throw std::bad_alloc();
    if (void *p = test_raw_allocate(n)) return p;
    throw std::bad_alloc();
}

void *operator new[](std::size_t n) {
    if (g_fail_next_new.exchange(0) != 0) throw std::bad_alloc();
    if (void *p = test_raw_allocate(n)) return p;
    throw std::bad_alloc();
}

void operator delete(void *p) noexcept { test_raw_deallocate(p); }
void operator delete[](void *p) noexcept { test_raw_deallocate(p); }
void operator delete(void *p, std::size_t) noexcept { test_raw_deallocate(p); }
void operator delete[](void *p, std::size_t) noexcept { test_raw_deallocate(p); }
void *operator new(std::size_t n, const std::nothrow_t &) noexcept {
    try { return ::operator new(n); } catch (...) { return nullptr; }
}
void *operator new[](std::size_t n, const std::nothrow_t &) noexcept {
    try { return ::operator new[](n); } catch (...) { return nullptr; }
}
void operator delete(void *p, const std::nothrow_t &) noexcept { test_raw_deallocate(p); }
void operator delete[](void *p, const std::nothrow_t &) noexcept { test_raw_deallocate(p); }

static void fail_next_allocation() { g_fail_next_new.store(1); }
static int cancel_pending_allocation_failure() { return g_fail_next_new.exchange(0); }

static int fails = 0, checks = 0;
static const char *cur = "?";
#define CHECK(cond, ...) do { checks++; if (!(cond)) { \
        std::printf("  FAIL [%s] %s:%d ", cur, __FILE__, __LINE__); std::printf(__VA_ARGS__); \
        std::putchar('\n'); fails++; } } while (0)
#define CASE(name) do { cur = (name); std::printf("- %s\n", cur); } while (0)

static const uint32_t D = ELPIS_EMBEDDING_DIM;
static std::string base;
static const char *kCorpusDg = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";

enum : size_t { OFF_FLAGS = 44, OFF_PAYLOAD_LEN = 48, OFF_HEADER_DG = 192, OFF_RESERVED = 224 };

static void put_u32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24);
}
static void reseal_header(std::vector<uint8_t> &img) {
    std::memset(img.data() + OFF_HEADER_DG, 0, 32);
    uint8_t d[32];
    elpis_sha256(img.data(), ELPIS_VSHARD_HEADER_BYTES, d);
    std::memcpy(img.data() + OFF_HEADER_DG, d, 32);
}
static void reseal_payload(std::vector<uint8_t> &img) {
    uint64_t paylen = 0;
    for (int i = 0; i < 8; i++) paylen |= (uint64_t)img[OFF_PAYLOAD_LEN + i] << (8 * i);
    uint8_t d[32];
    elpis_sha256(img.data() + ELPIS_VSHARD_HEADER_BYTES, (size_t)paylen, d);
    std::memcpy(img.data() + 160, d, 32);
    reseal_header(img);
}

/* Build a shard with an explicit namespace so two shards can be made
 * byte-compatible in size but different in metadata. */
static std::vector<uint8_t> build_ns_shard(elpis_embedder *emb, const char *tag, const char *ns,
                                           uint32_t n, char digest_out[65]) {
    std::vector<std::string> chunk(n), doc(n);
    std::vector<std::vector<float>> vec(n);
    std::vector<elpis_vshard_input> in(n);
    elpis_embedding_profile prof;
    elpis_embedder_profile(emb, &prof);
    for (uint32_t i = 0; i < n; i++) {
        char b[96];
        std::snprintf(b, sizeof b, "%s/chunk/%u", tag, i);
        chunk[i] = r2t::hex_of(b);
        std::snprintf(b, sizeof b, "%s/doc/%u", tag, i);
        doc[i] = r2t::hex_of(b);
        vec[i].resize(D);
        std::snprintf(b, sizeof b, "%s/body/%u", tag, i);
        elpis_embedder_embed(emb, b, std::strlen(b), vec[i].data(), D);
        std::snprintf(in[i].chunk_digest, sizeof in[i].chunk_digest, "%s", chunk[i].c_str());
        std::snprintf(in[i].doc_digest, sizeof in[i].doc_digest, "%s", doc[i].c_str());
        in[i].ns = ns;
        in[i].authority = "reference";
        in[i].vector = vec[i].data();
    }
    void *bytes = nullptr;
    size_t len = 0;
    if (elpis_vshard_build(in.data(), n, &prof, kCorpusDg, &bytes, &len, digest_out) != 0) return {};
    std::vector<uint8_t> img((uint8_t *)bytes, (uint8_t *)bytes + len);
    std::free(bytes);
    return img;
}

/* --------------------------------------------------------------- case 1 --- */

static void case_fixed_field_overread() {
    CASE("1: unterminated fixed-width digest fields are rejected without over-reading");
    /* Exactly sized heap allocation: any read past the final field is a
     * heap-buffer-overflow that AddressSanitizer will report. */
    elpis_embedding_profile *p =
        (elpis_embedding_profile *)std::malloc(sizeof(elpis_embedding_profile));
    CHECK(p != nullptr, "malloc");
    if (!p) return;

    elpis_embedder *e = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &e);
    elpis_embedder_profile(e, p);

    /* tokenizer_digest is the last member: filling all 65 bytes leaves no
     * terminator between it and the end of the allocation. */
    std::memset(p->tokenizer_digest, 'a', sizeof p->tokenizer_digest);
    CHECK(elpis_embedding_profile_validate(p) != 0, "unterminated tokenizer_digest accepted");
    char dg[65];
    CHECK(elpis_embedding_profile_digest(p, dg) != 0, "digest computed over an unterminated field");

    elpis_embedder_profile(e, p);
    std::memset(p->model_digest, 'b', sizeof p->model_digest);
    CHECK(elpis_embedding_profile_validate(p) != 0, "unterminated model_digest accepted");

    /* Non-hex and wrong-length fields. */
    elpis_embedder_profile(e, p);
    p->model_digest[10] = 'z';
    CHECK(elpis_embedding_profile_validate(p) != 0, "non-hex digest accepted");
    elpis_embedder_profile(e, p);
    p->model_digest[63] = '\0';
    CHECK(elpis_embedding_profile_validate(p) != 0, "63-character digest accepted");

    /* Unterminated text fields too. */
    elpis_embedder_profile(e, p);
    std::memset(p->name, 'n', sizeof p->name);
    CHECK(elpis_embedding_profile_validate(p) != 0, "unterminated name accepted");
    elpis_embedder_profile(e, p);
    std::memset(p->backend, 'k', sizeof p->backend);
    CHECK(elpis_embedding_profile_validate(p) != 0, "unterminated backend accepted");

    elpis_embedder_destroy(e);
    std::free(p);
}

/* --------------------------------------------------------------- case 2 --- */

static void case_same_address_metadata() {
    CASE("2: metadata cache is keyed on content, not on the buffer address");
    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    char da[65], db[65];
    std::vector<uint8_t> A = build_ns_shard(emb, "alpha", "aaa", 8, da);
    std::vector<uint8_t> B = build_ns_shard(emb, "beta", "bbb", 8, db);
    CHECK(!A.empty() && !B.empty(), "build both shards");
    CHECK(A.size() == B.size(), "shards differ in size (%zu vs %zu), cannot share an address",
          A.size(), B.size());
    if (A.empty() || B.empty() || A.size() != B.size()) { elpis_embedder_destroy(emb); return; }

    /* One buffer, used for A and then overwritten in place by B. */
    void *buf = std::malloc(A.size());
    CHECK(buf != nullptr, "malloc");
    if (!buf) { elpis_embedder_destroy(emb); return; }

    std::memcpy(buf, A.data(), A.size());
    CHECK(elpis_vshard_verify(buf, A.size(), nullptr, nullptr, 0) == 0, "verify A");
    const char *ns = nullptr, *au = nullptr;
    CHECK(elpis_vshard_record_meta(buf, A.size(), 0, &ns, &au) == 0, "meta A");
    CHECK(ns && std::strcmp(ns, "aaa") == 0, "shard A namespace is '%s', expected 'aaa'", ns ? ns : "");

    std::memcpy(buf, B.data(), B.size());
    CHECK(elpis_vshard_verify(buf, B.size(), nullptr, nullptr, 0) == 0, "verify B");
    ns = nullptr;
    CHECK(elpis_vshard_record_meta(buf, B.size(), 0, &ns, &au) == 0, "meta B");
    CHECK(ns && std::strcmp(ns, "bbb") == 0,
          "stale metadata: same address returned '%s' after replacement, expected 'bbb'",
          ns ? ns : "");

    /* And back again, to prove the key is not simply a one-shot invalidation. */
    std::memcpy(buf, A.data(), A.size());
    ns = nullptr;
    elpis_vshard_record_meta(buf, A.size(), 0, &ns, &au);
    CHECK(ns && std::strcmp(ns, "aaa") == 0, "returning to shard A gave '%s'", ns ? ns : "");

    std::free(buf);
    elpis_embedder_destroy(emb);
}

/* --------------------------------------------------------------- case 3 --- */

static void case_verify_missing_shard() {
    CASE("3: verifying an absent shard reports NOTFOUND, not OK");
    fms_ctx *fms = r2t::make_fms(base + "/verify", 8ull << 20);
    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile prof;
    elpis_embedder_profile(emb, &prof);
    elpis_vector_index *ix = nullptr;
    elpis_vector_index_create(fms, &prof, kCorpusDg, &ix);

    const char *absent = "1111111111111111111111111111111111111111111111111111111111111111";

    /* Empty index. */
    CHECK(elpis_vector_index_verify(ix, nullptr) == ELPIS_VEC_OK, "empty index, NULL digest");
    CHECK(elpis_vector_index_verify(ix, absent) == ELPIS_VEC_E_NOTFOUND,
          "empty index, absent digest returned OK");

    /* Populated index. */
    r2t::Corpus c;
    c.build("verify", 32, emb);
    char sd[65];
    std::vector<uint8_t> img = r2t::build_shard(c, kCorpusDg, sd);
    CHECK(elpis_vector_index_add_shard_bytes(ix, img.data(), img.size(), nullptr) == ELPIS_VEC_OK,
          "admit");
    CHECK(elpis_vector_index_verify(ix, nullptr) == ELPIS_VEC_OK, "all shards");
    CHECK(elpis_vector_index_verify(ix, sd) == ELPIS_VEC_OK, "present digest");
    CHECK(elpis_vector_index_verify(ix, absent) == ELPIS_VEC_E_NOTFOUND, "absent digest");

    /* Malformed digests. */
    CHECK(elpis_vector_index_verify(ix, "short") == ELPIS_VEC_E_INVAL, "short digest");
    CHECK(elpis_vector_index_verify(ix, "ZZZZ111111111111111111111111111111111111111111111111111111111111")
              == ELPIS_VEC_E_INVAL, "non-hex digest");
    std::string upper(sd);
    for (char &ch : upper) ch = (char)std::toupper((unsigned char)ch);
    CHECK(elpis_vector_index_verify(ix, upper.c_str()) == ELPIS_VEC_E_INVAL,
          "uppercase digest was not rejected as malformed");

    /* inspect and shard_object follow the same rules. */
    elpis_vshard_header h;
    CHECK(elpis_vector_index_inspect(ix, absent, &h) == ELPIS_VEC_E_NOTFOUND, "inspect absent");
    CHECK(elpis_vector_index_inspect(ix, "nope", &h) == ELPIS_VEC_E_INVAL, "inspect malformed");
    fms_id id = 0;
    CHECK(elpis_vector_index_shard_object(ix, absent, &id) == ELPIS_VEC_E_NOTFOUND,
          "shard_object absent");

    elpis_vector_index_destroy(ix);
    fms_destroy(fms);
    elpis_embedder_destroy(emb);
}

/* --------------------------------------------------------------- case 4 --- */

static void case_filter_validation() {
    CASE("4: invalid namespace and authority filters fail, they do not return empty");
    std::string root = base + "/filters";
    elpis_corpus *corpus = nullptr;
    CHECK(elpis_corpus_open((root + "/state").c_str(), &corpus) == 0, "corpus open");
    if (!corpus) return;

    const char *body = "ELPIS_ROOT_A is the active root filesystem for this host.\n";
    elpis_ingest_meta m;
    std::memset(&m, 0, sizeof m);
    m.ns = "elpis.docs";
    m.authority = "canonical";
    m.media_type = ELPIS_MT_TEXT;
    m.origin = "a.txt";
    elpis_ingest_result r;
    CHECK(elpis_corpus_ingest_bytes(corpus, body, std::strlen(body), &m, &r) == 0, "ingest");

    elpis_chunk_ref refs[8];
    uint32_t n = 99;
    CHECK(elpis_corpus_list_chunks(corpus, nullptr, nullptr, 0, 8, refs, &n) == 0, "unfiltered");
    CHECK(n >= 1, "no chunks enumerated");

    /* Unknown authority class must fail, not silently return zero rows. */
    n = 99;
    CHECK(elpis_corpus_list_chunks(corpus, nullptr, "bogus", 0, 8, refs, &n) != 0,
          "unknown authority class accepted");
    n = 99;
    CHECK(elpis_corpus_list_chunks(corpus, nullptr, "untrusted", 0, 8, refs, &n) != 0,
          "authority class outside the declared four accepted");
    /* The four declared classes are accepted. */
    for (const char *a : {"canonical", "reference", "advisory", "provisional"}) {
        n = 99;
        CHECK(elpis_corpus_list_chunks(corpus, nullptr, a, 0, 8, refs, &n) == 0,
              "declared authority '%s' rejected", a);
    }
    /* Namespace policy matches R1 lexical search: printable, bounded, non-empty. */
    n = 99;
    CHECK(elpis_corpus_list_chunks(corpus, "bad\x01ns", nullptr, 0, 8, refs, &n) != 0,
          "control character in namespace accepted");
    n = 99;
    CHECK(elpis_corpus_list_chunks(corpus, "", nullptr, 0, 8, refs, &n) != 0,
          "empty namespace accepted");
    std::string too_long(200, 'x');
    n = 99;
    CHECK(elpis_corpus_list_chunks(corpus, too_long.c_str(), nullptr, 0, 8, refs, &n) != 0,
          "oversized namespace accepted");
    /* R1 lexical search must behave identically: same policy, same answers. */
    elpis_hit hits[8];
    uint32_t hn = 0;
    CHECK(elpis_corpus_search_lexical(corpus, "ELPIS_ROOT_A", nullptr, "bogus", 8, hits, &hn) != 0,
          "R1 lexical search accepted an unknown authority class");
    elpis_corpus_close(corpus);

    /* Vector search applies the same policy. */
    fms_ctx *fms = r2t::make_fms(base + "/filters-fms", 8ull << 20);
    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile prof;
    elpis_embedder_profile(emb, &prof);
    elpis_vector_index *ix = nullptr;
    elpis_vector_index_create(fms, &prof, kCorpusDg, &ix);
    r2t::Corpus c;
    c.build("filters", 16, emb);
    char sd[65];
    std::vector<uint8_t> img = r2t::build_shard(c, kCorpusDg, sd);
    elpis_vector_index_add_shard_bytes(ix, img.data(), img.size(), nullptr);

    elpis_vector_query q;
    std::memset(&q, 0, sizeof q);
    q.vector = c.vec[0].data();
    q.dimensions = D;
    q.k = 4;
    std::vector<elpis_vector_hit> vh(4);
    uint32_t vn = 99;
    q.authority_filter = "bogus";
    CHECK(elpis_vector_index_search(ix, &q, vh.data(), &vn) == ELPIS_VEC_E_INVAL,
          "vector search accepted an unknown authority class");
    CHECK(vn == 0, "invalid filter still produced %u hits", vn);
    q.authority_filter = nullptr;
    q.ns_filter = "bad\x01ns";
    CHECK(elpis_vector_index_search(ix, &q, vh.data(), &vn) == ELPIS_VEC_E_INVAL,
          "vector search accepted a control character in the namespace filter");
    q.ns_filter = "elpis.docs";
    CHECK(elpis_vector_index_search(ix, &q, vh.data(), &vn) == ELPIS_VEC_OK, "valid filter rejected");

    elpis_vector_index_destroy(ix);
    fms_destroy(fms);
    elpis_embedder_destroy(emb);
}

/* --------------------------------------------------------------- case 5 --- */

static void case_atomic_publication() {
    CASE("5: shard publication is atomically no-replace under two concurrent writers");
    std::string dir = base + "/publish";
    r2t::mkdirp(dir);
    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    char d1[65], d2[65];
    std::vector<uint8_t> A = build_ns_shard(emb, "pub-a", "aaa", 6, d1);
    std::vector<uint8_t> B = build_ns_shard(emb, "pub-b", "bbb", 6, d2);
    CHECK(!A.empty() && !B.empty(), "build");
    if (A.empty() || B.empty()) { elpis_embedder_destroy(emb); return; }

    std::string path = dir + "/contested.vshard";
    std::atomic<int> ok_a{0}, ok_b{0};
    std::thread ta([&] { ok_a = elpis_vshard_write(path.c_str(), A.data(), A.size()) == 0 ? 1 : 0; });
    std::thread tb([&] { ok_b = elpis_vshard_write(path.c_str(), B.data(), B.size()) == 0 ? 1 : 0; });
    ta.join();
    tb.join();

    CHECK(ok_a + ok_b == 1, "exactly one writer must win, got a=%d b=%d", ok_a.load(), ok_b.load());

    /* The winner's bytes must be complete and verifiable. */
    void *rb = nullptr;
    size_t rn = 0;
    CHECK(elpis_vshard_read_file(path.c_str(), &rb, &rn) == 0, "read published shard");
    if (rb) {
        elpis_vshard_header h;
        char reason[64] = {0};
        CHECK(elpis_vshard_verify(rb, rn, &h, reason, sizeof reason) == 0,
              "published shard failed verification: %s", reason);
        bool is_a = rn == A.size() && std::memcmp(rb, A.data(), rn) == 0;
        bool is_b = rn == B.size() && std::memcmp(rb, B.data(), rn) == 0;
        CHECK(is_a || is_b, "published bytes match neither writer: torn publication");
        CHECK(is_a == (ok_a.load() == 1), "the file does not belong to the writer that reported success");
        std::free(rb);
    }

    /* A later write to the same path always fails. */
    CHECK(elpis_vshard_write(path.c_str(), A.data(), A.size()) != 0, "overwrite allowed");

    /* No temporary files survive on any path. */
    int leftovers = 0;
    DIR *dh = opendir(dir.c_str());
    if (dh) {
        struct dirent *e;
        while ((e = readdir(dh)))
            if (std::strncmp(e->d_name, ".vshard-", 8) == 0) leftovers++;
        closedir(dh);
    }
    CHECK(leftovers == 0, "%d temporary file(s) left behind", leftovers);
    elpis_embedder_destroy(emb);
}

/* --------------------------------------------------------------- case 6 --- */

static void case_canonical_digests() {
    CASE("6: digest identities must be canonical lowercase hex");
    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile prof;
    elpis_embedder_profile(emb, &prof);

    r2t::Corpus c;
    c.build("canon", 6, emb);

    /* Uppercase chunk digest is rejected outright, never folded. */
    {
        r2t::Corpus g = c;
        std::string up = g.chunk[2];
        for (char &ch : up) ch = (char)std::toupper((unsigned char)ch);
        g.chunk[2] = up;
        g.refresh();
        void *b = nullptr;
        size_t n = 0;
        char dg[65];
        CHECK(elpis_vshard_build(g.inputs.data(), g.inputs.size(), &prof, kCorpusDg, &b, &n, dg) != 0,
              "uppercase chunk digest accepted");
        if (b) std::free(b);
    }
    /* Uppercase document digest likewise. */
    {
        r2t::Corpus g = c;
        std::string up = g.doc[1];
        for (char &ch : up) ch = (char)std::toupper((unsigned char)ch);
        g.doc[1] = up;
        g.refresh();
        void *b = nullptr;
        size_t n = 0;
        char dg[65];
        CHECK(elpis_vshard_build(g.inputs.data(), g.inputs.size(), &prof, kCorpusDg, &b, &n, dg) != 0,
              "uppercase document digest accepted");
        if (b) std::free(b);
    }
    /* Mixed-case duplicate: the same identity spelled two ways must not become
     * two records. It is refused as non-canonical rather than deduplicated. */
    {
        r2t::Corpus g = c;
        std::string mixed = g.chunk[0];
        for (size_t i = 0; i < mixed.size(); i += 2)
            mixed[i] = (char)std::toupper((unsigned char)mixed[i]);
        g.chunk[3] = mixed;
        g.refresh();
        void *b = nullptr;
        size_t n = 0;
        char dg[65];
        CHECK(elpis_vshard_build(g.inputs.data(), g.inputs.size(), &prof, kCorpusDg, &b, &n, dg) != 0,
              "mixed-case duplicate identity accepted as a distinct record");
        if (b) std::free(b);
    }
    /* Non-hex and short digests. */
    {
        r2t::Corpus g = c;
        g.chunk[1] = std::string(63, 'a');
        g.refresh();
        void *b = nullptr;
        size_t n = 0;
        char dg[65];
        CHECK(elpis_vshard_build(g.inputs.data(), g.inputs.size(), &prof, kCorpusDg, &b, &n, dg) != 0,
              "63-character digest accepted");
        if (b) std::free(b);
    }
    /* Corpus manifest binding must be canonical too. */
    {
        void *b = nullptr;
        size_t n = 0;
        char dg[65];
        std::string up(kCorpusDg);
        for (char &ch : up) ch = (char)std::toupper((unsigned char)ch);
        CHECK(elpis_vshard_build(c.inputs.data(), c.inputs.size(), &prof, up.c_str(), &b, &n, dg) != 0,
              "uppercase corpus manifest digest accepted");
        if (b) std::free(b);
    }
    /* Index corpus binding must be canonical. */
    {
        fms_ctx *fms = r2t::make_fms(base + "/canon-fms", 4ull << 20);
        elpis_vector_index *ix = nullptr;
        std::string up(kCorpusDg);
        for (char &ch : up) ch = (char)std::toupper((unsigned char)ch);
        CHECK(elpis_vector_index_create(fms, &prof, up.c_str(), &ix) != 0,
              "index accepted an uppercase corpus binding");
        CHECK(elpis_vector_index_create(fms, &prof, "short", &ix) != 0,
              "index accepted a short corpus binding");
        fms_destroy(fms);
    }
    elpis_embedder_destroy(emb);
}

/* --------------------------------------------------------------- case 7 --- */

static void case_profile_reserved() {
    CASE("7: profile reserved field must be zero");
    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile p;
    elpis_embedder_profile(emb, &p);
    CHECK(elpis_embedding_profile_validate(&p) == 0, "clean profile rejected");

    p.reserved = 1;
    CHECK(elpis_embedding_profile_validate(&p) != 0, "nonzero reserved accepted");
    char dg[65];
    CHECK(elpis_embedding_profile_digest(&p, dg) != 0, "digest computed for an invalid profile");

    elpis_embedder *ext = nullptr;
    CHECK(elpis_embedder_external_create(&p, &ext) != 0, "external provider accepted reserved != 0");
    elpis_embedder_destroy(emb);
}

/* ------------------------------------------------------------ cases 8, 9 --- */

static void case_shard_flags_reserved_l2() {
    CASE("8/9: unknown flags, nonzero reserved bytes, and L2 policy violations");
    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    char sd[65];
    std::vector<uint8_t> ok = build_ns_shard(emb, "flags", "elpis.docs", 8, sd);
    CHECK(!ok.empty(), "build");
    if (ok.empty()) { elpis_embedder_destroy(emb); return; }

    char reason[64];
    {
        auto v = ok;
        put_u32(v.data() + OFF_FLAGS, 1);
        reseal_header(v);
        std::memset(reason, 0, sizeof reason);
        CHECK(elpis_vshard_verify(v.data(), v.size(), nullptr, reason, sizeof reason) != 0,
              "unknown flag bit accepted");
        CHECK(std::strcmp(reason, "unknown_flags") == 0, "flags reason '%s'", reason);
    }
    {
        auto v = ok;
        v[OFF_RESERVED + 7] = 0x01;
        reseal_header(v);
        std::memset(reason, 0, sizeof reason);
        CHECK(elpis_vshard_verify(v.data(), v.size(), nullptr, reason, sizeof reason) != 0,
              "nonzero reserved header bytes accepted");
        CHECK(std::strcmp(reason, "nonzero_reserved") == 0, "reserved reason '%s'", reason);
    }
    /* A shard that declares L2 but stores a scaled vector. */
    {
        auto v = ok;
        uint8_t *vec = v.data() + ELPIS_VSHARD_HEADER_BYTES + 64;
        for (uint32_t d = 0; d < D; d++) {
            float f;
            uint32_t bits = (uint32_t)vec[d * 4] | ((uint32_t)vec[d * 4 + 1] << 8) |
                            ((uint32_t)vec[d * 4 + 2] << 16) | ((uint32_t)vec[d * 4 + 3] << 24);
            std::memcpy(&f, &bits, 4);
            f *= 3.0f;
            std::memcpy(&bits, &f, 4);
            put_u32(vec + d * 4, bits);
        }
        reseal_payload(v);
        std::memset(reason, 0, sizeof reason);
        CHECK(elpis_vshard_verify(v.data(), v.size(), nullptr, reason, sizeof reason) != 0,
              "L2 policy violation accepted");
        CHECK(std::strcmp(reason, "l2_policy_violation") == 0, "L2 reason '%s'", reason);
    }
    /* An all-zero vector under an L2 profile. */
    {
        auto v = ok;
        std::memset(v.data() + ELPIS_VSHARD_HEADER_BYTES + 64, 0, (size_t)D * 4);
        reseal_payload(v);
        std::memset(reason, 0, sizeof reason);
        CHECK(elpis_vshard_verify(v.data(), v.size(), nullptr, reason, sizeof reason) != 0,
              "zero vector accepted under an L2 profile");
        CHECK(std::strcmp(reason, "zero_norm_vector") == 0, "zero-norm reason '%s'", reason);
    }
    /* Builder-side: an unknown authority class and a control character in a namespace. */
    {
        r2t::Corpus c;
        c.build("semantic", 4, emb);
        elpis_embedding_profile prof;
        elpis_embedder_profile(emb, &prof);
        void *b = nullptr;
        size_t n = 0;
        char dg[65];
        auto g = c;
        g.authority[1] = "untrusted";
        g.refresh();
        CHECK(elpis_vshard_build(g.inputs.data(), g.inputs.size(), &prof, kCorpusDg, &b, &n, dg) != 0,
              "unknown authority class accepted into a shard");
        if (b) { std::free(b); b = nullptr; }
        auto g2 = c;
        g2.ns[0] = std::string("bad\x01ns");
        g2.refresh();
        CHECK(elpis_vshard_build(g2.inputs.data(), g2.inputs.size(), &prof, kCorpusDg, &b, &n, dg) != 0,
              "control character in namespace accepted into a shard");
        if (b) std::free(b);
    }
    elpis_embedder_destroy(emb);
}

/* -------------------------------------------------------------- case 10 --- */

static void case_read_accessor_concurrency() {
    CASE("10: read accessors are safe against concurrent admission and close");
    fms_ctx *fms = r2t::make_fms(base + "/accessors", 16ull << 20);
    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile prof;
    elpis_embedder_profile(emb, &prof);
    elpis_vector_index *ix = nullptr;
    elpis_vector_index_create(fms, &prof, kCorpusDg, &ix);

    std::vector<std::vector<uint8_t>> imgs;
    std::vector<std::string> digests;
    for (int i = 0; i < 6; i++) {
        char tag[32];
        std::snprintf(tag, sizeof tag, "acc-%d", i);
        char sd[65];
        imgs.push_back(build_ns_shard(emb, tag, "elpis.docs", 24, sd));
        digests.emplace_back(sd);
    }

    std::atomic<int> bad{0};
    std::atomic<bool> stop{false};

    /* Readers hammer every accessor the audit named. */
    auto reader = [&]() {
        while (!stop.load()) {
            uint32_t count = elpis_vector_index_shard_count(ix);
            if (count > 6) { bad++; return; }
            char ids[8][65];
            uint32_t n = 0;
            if (elpis_vector_index_list_shards(ix, ids, 8, &n) == ELPIS_VEC_OK) {
                if (n > 6) { bad++; return; }
                for (uint32_t i = 1; i < n; i++)
                    if (std::strcmp(ids[i - 1], ids[i]) >= 0) { bad++; return; }
            }
            char pd[65] = {0}, cd[65] = {0};
            if (elpis_vector_index_profile_digest(ix, pd, cd) != ELPIS_VEC_OK) { bad++; return; }
            if (std::strlen(pd) != 64 || std::strlen(cd) != 64) { bad++; return; }
            fms_id id = 0;
            elpis_vector_index_shard_object(ix, digests[0].c_str(), &id);
            char *json = nullptr;
            char mdg[65];
            if (elpis_vector_index_manifest_json(ix, &json, mdg) == 0 && json) std::free(json);
        }
    };

    std::vector<std::thread> readers;
    for (int i = 0; i < 3; i++) readers.emplace_back(reader);

    /* Writer churns admission and close underneath them. */
    for (int round = 0; round < 3; round++) {
        for (size_t i = 0; i < imgs.size(); i++)
            elpis_vector_index_add_shard_bytes(ix, imgs[i].data(), imgs[i].size(), nullptr);
        for (size_t i = 0; i < digests.size(); i++)
            elpis_vector_index_close_shard(ix, digests[i].c_str());
    }
    stop.store(true);
    for (auto &t : readers) t.join();

    CHECK(bad.load() == 0, "%d read accessor inconsistency(ies) observed", bad.load());
    CHECK(elpis_vector_index_shard_count(ix) == 0, "shards remain after the final close round");

    elpis_vector_index_destroy(ix);
    fms_destroy(fms);
    elpis_embedder_destroy(emb);
}

/* -------------------------------------------------------------- case 11 --- */

static void case_bounded_score_domain() {
    CASE("11: searchable indexes are L2-bound and canonical ranking cannot saturate");

    fms_ctx *fms = r2t::make_fms(base + "/score-domain", 8ull << 20);
    CHECK(fms != nullptr, "fms");
    if (!fms) return;

    /* Provider qualification may expose NORM_NONE, but an index may not. */
    elpis_embedder *raw = nullptr;
    CHECK(elpis_embedder_fixture_create(ELPIS_NORM_NONE, &raw) == 0, "raw fixture create");
    elpis_embedding_profile raw_profile{};
    CHECK(elpis_embedder_profile(raw, &raw_profile) == 0, "raw profile");
    elpis_vector_index *ix = reinterpret_cast<elpis_vector_index *>(uintptr_t{1});
    CHECK(elpis_vector_index_create(fms, &raw_profile, kCorpusDg, &ix) == ELPIS_VEC_E_PROFILE,
          "NORM_NONE + DOT index was admitted");
    CHECK(ix == nullptr, "failed index creation left a non-null output");

    /* Huge finite vectors are refused by the L2 provider boundary too. */
    elpis_embedder *l2 = nullptr;
    CHECK(elpis_embedder_fixture_create(ELPIS_NORM_L2, &l2) == 0, "l2 fixture create");
    elpis_embedding_profile prof{};
    CHECK(elpis_embedder_profile(l2, &prof) == 0, "l2 profile");
    prof.metric = ELPIS_METRIC_DOT;  /* valid only because normalization remains L2 */
    elpis_embedder *ext = nullptr;
    CHECK(elpis_embedder_external_create(&prof, &ext) == 0, "external create");
    std::vector<float> huge(D, 1.0e20f), admitted(D, 0.0f);
    CHECK(elpis_embedder_accept(ext, huge.data(), D, nullptr, admitted.data(), D) != 0,
          "very large finite raw vector entered an L2 profile");

    /* Two valid unit vectors: the lower score owns the lexicographically smaller
     * chunk digest, so a score-key collision would reverse the true order. */
    std::vector<float> low(D, 0.0f), high(D, 0.0f), query(D, 0.0f);
    low[0] = 0.6f;  low[1] = 0.8f;
    high[0] = 0.8f; high[1] = 0.6f;
    query[0] = 1.0f;

    elpis_vshard_input recs[2]{};
    std::snprintf(recs[0].chunk_digest, sizeof recs[0].chunk_digest,
                  "0000000000000000000000000000000000000000000000000000000000000001");
    std::snprintf(recs[0].doc_digest, sizeof recs[0].doc_digest,
                  "1111111111111111111111111111111111111111111111111111111111111111");
    recs[0].ns = "elpis.docs";
    recs[0].authority = "reference";
    recs[0].vector = low.data();
    std::snprintf(recs[1].chunk_digest, sizeof recs[1].chunk_digest,
                  "fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffe");
    std::snprintf(recs[1].doc_digest, sizeof recs[1].doc_digest,
                  "2222222222222222222222222222222222222222222222222222222222222222");
    recs[1].ns = "elpis.docs";
    recs[1].authority = "reference";
    recs[1].vector = high.data();

    void *bytes = nullptr;
    size_t len = 0;
    char shard_digest[65]{};
    CHECK(elpis_vshard_build(recs, 2, &prof, kCorpusDg, &bytes, &len, shard_digest) == 0,
          "build normalized DOT shard");
    ix = nullptr;
    CHECK(elpis_vector_index_create(fms, &prof, kCorpusDg, &ix) == ELPIS_VEC_OK,
          "L2 + DOT index rejected");
    CHECK(ix != nullptr, "L2 index missing");
    if (ix && bytes) {
        CHECK(elpis_vector_index_add_shard_bytes(ix, bytes, len, nullptr) == ELPIS_VEC_OK,
              "admit normalized DOT shard");
        elpis_vector_query q{};
        q.vector = query.data(); q.dimensions = D; q.k = 2;
        elpis_vector_hit hits[2]{};
        uint32_t n = 0;
        CHECK(elpis_vector_index_search(ix, &q, hits, &n) == ELPIS_VEC_OK, "DOT search");
        CHECK(n == 2, "expected two hits, got %u", n);
        if (n == 2) {
            CHECK(std::strcmp(hits[0].chunk_digest, recs[1].chunk_digest) == 0,
                  "lower score ranked first after canonicalization");
            CHECK(hits[0].score > hits[1].score, "raw diagnostic scores not ordered");
            CHECK(hits[0].score_key > hits[1].score_key, "valid score keys collided or reversed");
        }
    }

    CHECK(elpis_vector_score_key(1.0e40) == ELPIS_VEC_SCORE_SCALE,
          "positive direct overshoot did not clamp");
    CHECK(elpis_vector_score_key(-1.0e40) == -ELPIS_VEC_SCORE_SCALE,
          "negative direct overshoot did not clamp");
    CHECK(elpis_vector_score_key(std::numeric_limits<double>::quiet_NaN()) ==
              std::numeric_limits<int64_t>::min(),
          "NaN did not map to the invalid lowest key");

    if (bytes) std::free(bytes);
    if (ix) elpis_vector_index_destroy(ix);
    elpis_embedder_destroy(ext);
    elpis_embedder_destroy(l2);
    elpis_embedder_destroy(raw);
    fms_destroy(fms);
}

/* -------------------------------------------------------------- case 12 --- */

static void case_exception_containment() {
    CASE("12: allocation failures never cross the public C ABI");

    elpis_embedder *emb = nullptr;
    CHECK(elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb) == 0, "fixture create");
    char sd[65]{};
    std::vector<uint8_t> img = build_ns_shard(emb, "alloc", "elpis.docs", 8, sd);
    CHECK(!img.empty(), "build shard");

    /* Verification allocates while parsing metadata. The public wrapper must
     * catch bad_alloc, name it, and leave the output wholly zeroed. */
    elpis_vshard_header h;
    std::memset(&h, 0xa5, sizeof h);
    char reason[64]{};
    bool crossed = false;
    int rc = 0;
    fail_next_allocation();
    try { rc = elpis_vshard_verify(img.data(), img.size(), &h, reason, sizeof reason); }
    catch (...) { crossed = true; }
    CHECK(!crossed, "elpis_vshard_verify allowed an exception across C ABI");
    CHECK(rc != 0, "allocation-failed verification returned success");
    CHECK(std::strcmp(reason, "allocation_failure") == 0,
          "allocation failure reason was '%s'", reason);
    const uint8_t *hb = reinterpret_cast<const uint8_t *>(&h);
    bool all_zero = true;
    for (size_t i = 0; i < sizeof h; i++) if (hb[i] != 0) { all_zero = false; break; }
    CHECK(all_zero, "failed verify partially populated its output header");
    cancel_pending_allocation_failure();

    /* Embedder error paths are now fixed-buffer and nonallocating. Arm the
     * allocator and prove the path returns normally without consuming it. */
    std::vector<float> v(D, 0.0f);
    fail_next_allocation();
    crossed = false;
    try { rc = elpis_embedder_embed(emb, "x", 1, v.data(), D - 1); }
    catch (...) { crossed = true; }
    CHECK(!crossed && rc != 0, "fixture embedder error escaped");
    CHECK(cancel_pending_allocation_failure() == 1,
          "fixture error path unexpectedly allocated");

    elpis_embedding_profile prof{};
    elpis_embedder_profile(emb, &prof);
    elpis_embedder *ext = nullptr;
    fail_next_allocation();
    crossed = false;
    try { rc = elpis_embedder_external_create(&prof, &ext); }
    catch (...) { crossed = true; }
    CHECK(!crossed, "external create allowed bad_alloc across C ABI");
    CHECK(rc != 0 && ext == nullptr, "allocation-failed external create succeeded");
    cancel_pending_allocation_failure();

    /* The close path previously allocated while formatting errors. It is now
     * guarded and fixed-buffer. Closing a real shard must remain successful
     * with the C++ allocator armed and must not consume the failure. */
    fms_ctx *fms = r2t::make_fms(base + "/alloc-close", 8ull << 20);
    elpis_vector_index *ix = nullptr;
    CHECK(elpis_vector_index_create(fms, &prof, kCorpusDg, &ix) == ELPIS_VEC_OK, "index create");
    CHECK(elpis_vector_index_add_shard_bytes(ix, img.data(), img.size(), nullptr) == ELPIS_VEC_OK,
          "add shard");
    fail_next_allocation();
    crossed = false;
    try { rc = elpis_vector_index_close_shard(ix, sd); }
    catch (...) { crossed = true; }
    CHECK(!crossed, "close_shard allowed an exception across C ABI");
    CHECK(rc == ELPIS_VEC_OK, "close_shard returned %d", rc);
    CHECK(cancel_pending_allocation_failure() == 1,
          "close_shard unexpectedly allocated on the success path");

    elpis_vector_index_destroy(ix);
    fms_destroy(fms);
    elpis_embedder_destroy(emb);
}

/* -------------------------------------------------------------- case 13 --- */

static void case_digest_operation_policy() {
    CASE("13: every digest-taking index operation applies one canonical policy");

    fms_ctx *fms = r2t::make_fms(base + "/digest-policy", 8ull << 20);
    elpis_embedder *emb = nullptr;
    elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb);
    elpis_embedding_profile prof{};
    elpis_embedder_profile(emb, &prof);
    elpis_vector_index *ix = nullptr;
    CHECK(elpis_vector_index_create(fms, &prof, kCorpusDg, &ix) == ELPIS_VEC_OK, "index");
    char sd[65]{};
    std::vector<uint8_t> img = build_ns_shard(emb, "digest-ops", "elpis.docs", 4, sd);
    CHECK(elpis_vector_index_add_shard_bytes(ix, img.data(), img.size(), nullptr) == ELPIS_VEC_OK,
          "add");

    std::string upper(sd);
    for (char &ch : upper) if (ch >= 'a' && ch <= 'f') ch = (char)(ch - 'a' + 'A');
    const char *malformed[] = {upper.c_str(), "short",
                               "gggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggggg"};
    for (const char *d : malformed) {
        elpis_vshard_header hdr{};
        fms_id id = 0;
        CHECK(elpis_vector_index_verify(ix, d) == ELPIS_VEC_E_INVAL,
              "verify malformed digest returned another status");
        CHECK(elpis_vector_index_inspect(ix, d, &hdr) == ELPIS_VEC_E_INVAL,
              "inspect malformed digest returned another status");
        CHECK(elpis_vector_index_shard_object(ix, d, &id) == ELPIS_VEC_E_INVAL,
              "shard_object malformed digest returned another status");
        CHECK(elpis_vector_index_close_shard(ix, d) == ELPIS_VEC_E_INVAL,
              "close malformed digest returned another status");
    }

    const char *absent = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    elpis_vshard_header hdr{};
    fms_id id = 0;
    CHECK(elpis_vector_index_verify(ix, absent) == ELPIS_VEC_E_NOTFOUND, "verify absent");
    CHECK(elpis_vector_index_inspect(ix, absent, &hdr) == ELPIS_VEC_E_NOTFOUND, "inspect absent");
    CHECK(elpis_vector_index_shard_object(ix, absent, &id) == ELPIS_VEC_E_NOTFOUND,
          "shard_object absent");
    CHECK(elpis_vector_index_close_shard(ix, absent) == ELPIS_VEC_E_NOTFOUND, "close absent");

    CHECK(elpis_vector_index_verify(ix, sd) == ELPIS_VEC_OK, "verify present");
    CHECK(elpis_vector_index_inspect(ix, sd, &hdr) == ELPIS_VEC_OK, "inspect present");
    CHECK(elpis_vector_index_shard_object(ix, sd, &id) == ELPIS_VEC_OK && id != 0,
          "shard_object present");
    CHECK(elpis_vector_index_close_shard(ix, sd) == ELPIS_VEC_OK, "close present");

    elpis_vector_index_destroy(ix);
    fms_destroy(fms);
    elpis_embedder_destroy(emb);
}

/* -------------------------------------------------------------- case 14 --- */

static void case_fixture_v2_identity() {
    CASE("14: fixture identity names the implemented v2 algorithm");
    elpis_embedder *emb = nullptr;
    CHECK(elpis_embedder_fixture_create(ELPIS_NORM_L2, &emb) == 0, "fixture create");
    elpis_embedding_profile p{};
    CHECK(elpis_embedder_profile(emb, &p) == 0, "profile");
    CHECK(std::strcmp(p.name, "fixture-sha256-v2") == 0,
          "profile name is '%s'", p.name);
    char dg[65]{};
    CHECK(elpis_embedding_profile_digest(&p, dg) == 0, "profile digest");
    CHECK(std::strcmp(dg, "68db7e3136ca715df91cf3bb059a51a921627419af7046f88b9d50525cafd1d5") == 0,
          "unexpected v2 profile digest %s", dg);
    elpis_embedder_destroy(emb);
}

int main(int argc, char **argv) {
    base = argc > 1 ? argv[1] : "/tmp/hacf-r2-adversarial";
    r2t::rmtree(base);
    r2t::mkdirp(base);
    std::printf("R2 adversarial suite (Remediation 02), root=%s\n", base.c_str());

    case_fixed_field_overread();
    case_same_address_metadata();
    case_verify_missing_shard();
    case_filter_validation();
    case_atomic_publication();
    case_canonical_digests();
    case_profile_reserved();
    case_shard_flags_reserved_l2();
    case_read_accessor_concurrency();
    case_bounded_score_domain();
    case_exception_containment();
    case_digest_operation_policy();
    case_fixture_v2_identity();

    std::printf("%d checks, %d failures\n", checks, fails);
    return fails != 0;
}
