/* test_r1_corpus.cpp - Gate R1 invariant suite. */
#include "elpis/corpus.h"
#include "elpis/chunking.h"
#include "elpis/sha256.h"

#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

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

static std::string base;

static void rmtree(const std::string &p) {
    DIR *d = opendir(p.c_str());
    if (!d) return;
    struct dirent *e;
    while ((e = readdir(d))) {
        if (!std::strcmp(e->d_name, ".") || !std::strcmp(e->d_name, "..")) continue;
        std::string q = p + "/" + e->d_name;
        if (unlink(q.c_str()) != 0) rmtree(q);
    }
    closedir(d);
    rmdir(p.c_str());
}

static int count_files(const std::string &p) {
    DIR *d = opendir(p.c_str());
    if (!d) return -1;
    struct dirent *e;
    int n = 0;
    while ((e = readdir(d))) {
        if (!std::strcmp(e->d_name, ".") || !std::strcmp(e->d_name, "..")) continue;
        n++;
    }
    closedir(d);
    return n;
}

static elpis_ingest_meta meta(const char *ns, const char *auth, const char *mt, const char *origin) {
    elpis_ingest_meta m;
    std::memset(&m, 0, sizeof m);
    m.ns = ns; m.authority = auth; m.media_type = mt; m.origin = origin;
    return m;
}

static const char *kElpisDoc =
    "# Elpis host qualification\n\n"
    "The external system drive exposes ELPIS_ROOT_A as the active root filesystem.\n"
    "Root B is reserved for A/B updates and must not be reformatted.\n\n"
    "## Gate status\n\n"
    "Gate G6.2 recorded state READY_FOR_TARGETED_REMEDIATION_EXECUTION for the\n"
    "MacBookAir7,2 host after the TRMRefinementProposal review.\n\n"
    "## Notes\n\n"
    "The internal APFS disk is untouched. Deployment originates from Ouroboros.\n";

static const char *kOtherDoc =
    "# Unrelated notes\n\n"
    "This document mentions nothing about roots, gates or proposals.\n"
    "It exists so that identifier queries can be checked for precision.\n";

/* ------------------------------------------------------------------ cases -- */

static void case_deterministic_identity() {
    CASE("identical bytes produce identical document and chunk digests");
    std::string a = base + "/det-a", b = base + "/det-b";
    elpis_corpus *ca = nullptr, *cb = nullptr;
    CHECK(elpis_corpus_open(a.c_str(), &ca) == 0, "open a");
    CHECK(elpis_corpus_open(b.c_str(), &cb) == 0, "open b");
    if (!ca || !cb) return;

    elpis_ingest_meta m = meta("elpis.docs", "reference", ELPIS_MT_MARKDOWN, "doc.md");
    elpis_ingest_result ra, rb;
    CHECK(elpis_corpus_ingest_bytes(ca, kElpisDoc, std::strlen(kElpisDoc), &m, &ra) == 0,
          "ingest a: %s", elpis_corpus_error(ca));
    CHECK(elpis_corpus_ingest_bytes(cb, kElpisDoc, std::strlen(kElpisDoc), &m, &rb) == 0, "ingest b");
    CHECK(std::string(ra.doc_digest) == rb.doc_digest, "doc digests differ");
    CHECK(ra.chunk_count == rb.chunk_count && ra.chunk_count > 1,
          "chunk counts differ or degenerate: %u vs %u", ra.chunk_count, rb.chunk_count);

    /* Chunk digests must match position by position. */
    elpis_chunk_profile prof;
    elpis_chunk_profile_default(&prof);
    elpis_chunk *x = nullptr, *y = nullptr;
    size_t nx = 0, ny = 0;
    elpis_chunk_document(kElpisDoc, std::strlen(kElpisDoc), ELPIS_MT_MARKDOWN, &prof, ra.doc_digest, &x, &nx);
    elpis_chunk_document(kElpisDoc, std::strlen(kElpisDoc), ELPIS_MT_MARKDOWN, &prof, rb.doc_digest, &y, &ny);
    CHECK(nx == ny, "re-chunk count differs");
    for (size_t i = 0; i < nx && i < ny; i++) {
        CHECK(std::string(x[i].digest) == y[i].digest, "chunk %zu digest differs", i);
        CHECK(x[i].byte_start == y[i].byte_start && x[i].byte_end == y[i].byte_end,
              "chunk %zu boundaries differ", i);
    }
    elpis_chunks_free(x);
    elpis_chunks_free(y);
    elpis_corpus_close(ca);
    elpis_corpus_close(cb);
}

static void case_idempotent_ingest() {
    CASE("duplicate ingestion is idempotent");
    std::string r = base + "/idem";
    elpis_corpus *c = nullptr;
    CHECK(elpis_corpus_open(r.c_str(), &c) == 0, "open");
    if (!c) return;
    elpis_ingest_meta m = meta("elpis.docs", "reference", ELPIS_MT_MARKDOWN, "doc.md");
    elpis_ingest_result r1, r2;
    CHECK(elpis_corpus_ingest_bytes(c, kElpisDoc, std::strlen(kElpisDoc), &m, &r1) == 0, "first");
    uint64_t d1 = 0, k1 = 0, d2 = 0, k2 = 0;
    elpis_corpus_counts(c, &d1, &k1);
    CHECK(r1.duplicate == 0, "first ingest flagged duplicate");
    CHECK(elpis_corpus_ingest_bytes(c, kElpisDoc, std::strlen(kElpisDoc), &m, &r2) == 0, "second");
    elpis_corpus_counts(c, &d2, &k2);
    CHECK(r2.duplicate == 1, "second ingest not flagged duplicate");
    CHECK(d1 == d2 && k1 == k2, "counts changed on re-ingest: %llu/%llu -> %llu/%llu",
          (unsigned long long)d1, (unsigned long long)k1, (unsigned long long)d2, (unsigned long long)k2);
    CHECK(std::string(r1.doc_digest) == r2.doc_digest, "digest changed");
    CHECK(count_files(r + "/corpus") == 1, "duplicate blob written");
    elpis_corpus_close(c);
}

static void case_identifier_retrieval() {
    CASE("exact identifier retrieval through FTS5");
    std::string r = base + "/fts";
    elpis_corpus *c = nullptr;
    CHECK(elpis_corpus_open(r.c_str(), &c) == 0, "open");
    if (!c) return;
    elpis_ingest_meta m1 = meta("elpis.docs", "reference", ELPIS_MT_MARKDOWN, "host.md");
    elpis_ingest_meta m2 = meta("elpis.docs", "reference", ELPIS_MT_MARKDOWN, "other.md");
    elpis_ingest_result res;
    elpis_corpus_ingest_bytes(c, kElpisDoc, std::strlen(kElpisDoc), &m1, &res);
    std::string target_doc = res.doc_digest;
    elpis_corpus_ingest_bytes(c, kOtherDoc, std::strlen(kOtherDoc), &m2, &res);

    const char *ids[] = {"ELPIS_ROOT_A", "TRMRefinementProposal", "G6.2", "MacBookAir7,2",
                         "READY_FOR_TARGETED_REMEDIATION_EXECUTION"};
    for (const char *id : ids) {
        elpis_hit hits[16];
        uint32_t n = 0;
        int rc = elpis_corpus_search_lexical(c, id, nullptr, nullptr, 16, hits, &n);
        CHECK(rc == 0, "search failed for %s: %s", id, elpis_corpus_error(c));
        CHECK(n >= 1, "no hit for identifier %s", id);
        if (n >= 1) CHECK(std::string(hits[0].doc_digest) == target_doc,
                          "identifier %s matched the wrong document", id);
        for (uint32_t i = 0; i < n; i++)
            CHECK(std::string(hits[i].doc_digest) == target_doc,
                  "identifier %s leaked an unrelated document", id);
    }
    /* Absent identifier must return nothing. */
    elpis_hit hits[8];
    uint32_t n = 0;
    elpis_corpus_search_lexical(c, "ELPIS_ROOT_Q", nullptr, nullptr, 8, hits, &n);
    CHECK(n == 0, "absent identifier returned %u hits", n);
    /* FTS5 operator syntax in user input must be treated as literal text. */
    CHECK(elpis_corpus_search_lexical(c, "elpis OR gate*", nullptr, nullptr, 8, hits, &n) == 0,
          "operator-like query failed");
    CHECK(n == 0, "FTS OR/prefix syntax executed instead of remaining literal (%u hits)", n);
    CHECK(elpis_corpus_search_lexical(c, "text:ELPIS_ROOT_A", nullptr, nullptr, 8, hits, &n) == 0,
          "column-selector-like query failed");
    CHECK(n == 0, "FTS column selector executed instead of remaining literal (%u hits)", n);
    elpis_corpus_close(c);
}

static void case_filters() {
    CASE("strict namespace and authority filtering");
    std::string r = base + "/filters";
    elpis_corpus *c = nullptr;
    CHECK(elpis_corpus_open(r.c_str(), &c) == 0, "open");
    if (!c) return;
    const char *docA = "shared term alpha ELPIS_ROOT_A in namespace one\n";
    const char *docB = "shared term alpha ELPIS_ROOT_A in namespace two\n";
    elpis_ingest_meta m1 = meta("ns.one", "canonical", ELPIS_MT_TEXT, "a.txt");
    elpis_ingest_meta m2 = meta("ns.two", "advisory", ELPIS_MT_TEXT, "b.txt");
    elpis_ingest_result res;
    CHECK(elpis_corpus_ingest_bytes(c, docA, std::strlen(docA), &m1, &res) == 0, "ingest a");
    CHECK(elpis_corpus_ingest_bytes(c, docB, std::strlen(docB), &m2, &res) == 0, "ingest b");

    elpis_hit hits[16];
    uint32_t n = 0;
    elpis_corpus_search_lexical(c, "alpha", nullptr, nullptr, 16, hits, &n);
    CHECK(n == 2, "unfiltered search returned %u", n);

    elpis_corpus_search_lexical(c, "alpha", "ns.one", nullptr, 16, hits, &n);
    CHECK(n == 1 && std::string(hits[0].ns) == "ns.one", "namespace filter leaked (%u hits)", n);

    elpis_corpus_search_lexical(c, "alpha", nullptr, "advisory", 16, hits, &n);
    CHECK(n == 1 && std::string(hits[0].authority) == "advisory", "authority filter leaked (%u hits)", n);

    elpis_corpus_search_lexical(c, "alpha", "ns.one", "advisory", 16, hits, &n);
    CHECK(n == 0, "contradictory filters returned %u hits", n);

    /* Unknown authority class must be refused at ingest. */
    elpis_ingest_meta bad = meta("ns.one", "trusted-ish", ELPIS_MT_TEXT, "c.txt");
    CHECK(elpis_corpus_ingest_bytes(c, docA, std::strlen(docA), &bad, &res) != 0,
          "unknown authority class accepted");
    elpis_corpus_close(c);
}

static void case_media_types() {
    CASE("deterministic chunking across supported media types");
    const char *json  = "[{\"a\":1,\"s\":\"x,y\"},{\"b\":[2,3]},{\"c\":\"}\"}]";
    const char *jsonl = "{\"r\":1}\n{\"r\":2}\n\n{\"r\":3}\n";
    const char *code  =
        "#include <stdio.h>\n\n"
        "static int helper(int x) {\n    return x + 1;\n}\n\n"
        "int main(void) {\n    printf(\"%d\\n\", helper(1));\n    return 0;\n}\n";
    struct { const char *mt; const char *data; size_t min_units; } cases[] = {
        {ELPIS_MT_JSON, json, 3}, {ELPIS_MT_JSONL, jsonl, 3}, {ELPIS_MT_CODE, code, 2},
    };
    elpis_chunk_profile prof;
    elpis_chunk_profile_default(&prof);
    prof.min_bytes = 0;                       /* do not pack: exercise the splitters */
    for (auto &t : cases) {
        elpis_chunk *a = nullptr, *b = nullptr;
        size_t na = 0, nb = 0;
        CHECK(elpis_chunk_document(t.data, std::strlen(t.data), t.mt, &prof, "deadbeef", &a, &na) == 0,
              "chunk %s", t.mt);
        CHECK(elpis_chunk_document(t.data, std::strlen(t.data), t.mt, &prof, "deadbeef", &b, &nb) == 0,
              "rechunk %s", t.mt);
        CHECK(na == nb, "%s unstable count %zu vs %zu", t.mt, na, nb);
        CHECK(na >= t.min_units, "%s produced %zu units, expected >= %zu", t.mt, na, t.min_units);
        for (size_t i = 0; i < na && i < nb; i++)
            CHECK(std::string(a[i].digest) == b[i].digest, "%s chunk %zu unstable", t.mt, i);
        /* Boundaries must cover the document without overlap. */
        for (size_t i = 1; i < na; i++)
            CHECK(a[i].byte_start >= a[i-1].byte_end, "%s chunks overlap at %zu", t.mt, i);
        elpis_chunks_free(a);
        elpis_chunks_free(b);
    }
    /* UTF-8 boundaries are never split. */
    std::string utf8;
    for (int i = 0; i < 4000; i++) utf8 += "\xc3\xa9";      /* e-acute */
    elpis_chunk *u = nullptr;
    size_t nu = 0;
    CHECK(elpis_chunk_document(utf8.data(), utf8.size(), ELPIS_MT_TEXT, &prof, "deadbeef", &u, &nu) == 0,
          "utf8 chunk");
    for (size_t i = 0; i < nu; i++)
        CHECK(u[i].byte_start % 2 == 0 && u[i].byte_end % 2 == 0,
              "chunk %zu split a UTF-8 sequence (%llu..%llu)", i,
              (unsigned long long)u[i].byte_start, (unsigned long long)u[i].byte_end);
    elpis_chunks_free(u);
}

static void case_corruption_rejected() {
    CASE("corrupt corpus blob is rejected, not repaired");
    std::string r = base + "/corrupt";
    elpis_corpus *c = nullptr;
    CHECK(elpis_corpus_open(r.c_str(), &c) == 0, "open");
    if (!c) return;
    elpis_ingest_meta m = meta("elpis.docs", "reference", ELPIS_MT_MARKDOWN, "host.md");
    elpis_ingest_result res;
    CHECK(elpis_corpus_ingest_bytes(c, kElpisDoc, std::strlen(kElpisDoc), &m, &res) == 0, "ingest");

    uint64_t ok = 0, bad = 0;
    CHECK(elpis_corpus_verify(c, &ok, &bad, nullptr, 0) == 0, "verify clean corpus");
    CHECK(ok == 1 && bad == 0, "clean verify reported ok=%llu bad=%llu",
          (unsigned long long)ok, (unsigned long long)bad);

    std::string blob = r + "/corpus/" + res.doc_digest + ".blob";
    int fd = open(blob.c_str(), O_RDWR);
    CHECK(fd >= 0, "open blob");
    if (fd >= 0) { unsigned char x = '#'; CHECK(pwrite(fd, &x, 1, 10) == 1, "corrupt byte"); close(fd); }

    void *raw = nullptr;
    size_t len = 0;
    CHECK(elpis_corpus_document_bytes(c, res.doc_digest, &raw, &len) != 0,
          "corrupt blob was returned to the caller");
    CHECK(raw == nullptr, "unverified bytes handed out");
    CHECK(elpis_corpus_verify(c, &ok, &bad, nullptr, 0) == 1, "verify missed the corruption");
    CHECK(bad == 1, "verify reported bad=%llu", (unsigned long long)bad);
    elpis_corpus_close(c);
}

static void case_manifest() {
    CASE("manifest is canonical, stable and immutable");
    std::string r = base + "/manifest";
    elpis_corpus *c = nullptr;
    CHECK(elpis_corpus_open(r.c_str(), &c) == 0, "open");
    if (!c) return;
    elpis_ingest_meta m = meta("elpis.docs", "canonical", ELPIS_MT_MARKDOWN, "host.md");
    elpis_ingest_result res;
    elpis_corpus_ingest_bytes(c, kElpisDoc, std::strlen(kElpisDoc), &m, &res);
    elpis_corpus_ingest_bytes(c, kOtherDoc, std::strlen(kOtherDoc), &m, &res);

    char *j1 = nullptr, *j2 = nullptr;
    char d1[65], d2[65];
    CHECK(elpis_corpus_manifest_json(c, &j1, d1) == 0, "manifest 1");
    CHECK(elpis_corpus_manifest_json(c, &j2, d2) == 0, "manifest 2");
    CHECK(std::string(j1 ? j1 : "") == std::string(j2 ? j2 : ""), "manifest not byte-stable");
    CHECK(std::string(d1) == d2, "manifest digest not stable");
    CHECK(std::strstr(j1, "\"chunk_count\":") == j1 + 1, "top-level keys not in canonical order");
    CHECK(std::strstr(j1, "nan") == nullptr && std::strstr(j1, "Infinity") == nullptr,
          "manifest contains a non-finite literal");
    elpis_free(j1);
    elpis_free(j2);

    std::string path = r + "/ingest-manifest.json";
    char dg[65];
    CHECK(elpis_corpus_manifest_write(c, path.c_str(), dg) == 0, "manifest write");
    CHECK(elpis_corpus_manifest_write(c, path.c_str(), dg) != 0, "manifest overwrite was allowed");
    elpis_corpus_close(c);
}

static void case_evidence_untouched() {
    CASE("no mutable file is written under the evidence root");
    std::string state = base + "/split-state", evidence = base + "/split-evidence";
    mkdir(evidence.c_str(), 0700);
    elpis_corpus *c = nullptr;
    CHECK(elpis_corpus_open(state.c_str(), &c) == 0, "open");
    if (!c) return;
    elpis_ingest_meta m = meta("elpis.docs", "canonical", ELPIS_MT_MARKDOWN, "host.md");
    elpis_ingest_result res;
    for (int i = 0; i < 3; i++) {
        std::string doc = std::string(kElpisDoc) + "\nvariant " + std::to_string(i) + "\n";
        elpis_corpus_ingest_bytes(c, doc.data(), doc.size(), &m, &res);
    }
    elpis_hit hits[8];
    uint32_t n = 0;
    elpis_corpus_search_lexical(c, "ELPIS_ROOT_A", nullptr, nullptr, 8, hits, &n);
    CHECK(n >= 1, "search after ingest");
    CHECK(count_files(evidence) == 0, "evidence root has %d entries after ingest",
          count_files(evidence));

    /* An immutable manifest copy is the only thing allowed under evidence. */
    std::string mpath = evidence + "/ingestion-manifest.json";
    char dg[65];
    CHECK(elpis_corpus_manifest_write(c, mpath.c_str(), dg) == 0, "manifest export");
    CHECK(count_files(evidence) == 1, "evidence root gained extra files");
    elpis_corpus_close(c);
    CHECK(count_files(evidence) == 1, "evidence touched on close");
}

static void case_chunk_text_verified() {
    CASE("chunk text is verified against its normalised digest");
    std::string r = base + "/chunktext";
    elpis_corpus *c = nullptr;
    CHECK(elpis_corpus_open(r.c_str(), &c) == 0, "open");
    if (!c) return;
    elpis_ingest_meta m = meta("elpis.docs", "reference", ELPIS_MT_MARKDOWN, "host.md");
    elpis_ingest_result res;
    elpis_corpus_ingest_bytes(c, kElpisDoc, std::strlen(kElpisDoc), &m, &res);
    elpis_hit hits[8];
    uint32_t n = 0;
    elpis_corpus_search_lexical(c, "ELPIS_ROOT_A", nullptr, nullptr, 8, hits, &n);
    CHECK(n >= 1, "search");
    if (n >= 1) {
        char *text = nullptr;
        CHECK(elpis_corpus_chunk_text(c, hits[0].chunk_digest, &text) == 0, "chunk text");
        CHECK(text && std::strstr(text, "ELPIS_ROOT_A") != nullptr, "chunk text lacks the identifier");
        elpis_free(text);
    }
    elpis_corpus_close(c);
}

int main(int argc, char **argv) {
    base = argc > 1 ? argv[1] : "/tmp/elpis-r1";
    rmtree(base);
    mkdir(base.c_str(), 0700);
    std::printf("Corpus R1 suite, root=%s\n", base.c_str());

    case_deterministic_identity();
    case_idempotent_ingest();
    case_identifier_retrieval();
    case_filters();
    case_media_types();
    case_corruption_rejected();
    case_manifest();
    case_evidence_untouched();
    case_chunk_text_verified();

    std::printf("%d checks, %d failures\n", checks, fails);
    return fails != 0;
}
