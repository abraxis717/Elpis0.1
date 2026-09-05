#include "regex_hacf_query_ingress.h"

#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

static void req(bool ok, const char *msg) {
    if (!ok) {
        std::cerr << "FAIL " << msg << "\n";
        std::exit(1);
    }
}

struct CorpusGuard {
    elpis_corpus *p = nullptr;
    ~CorpusGuard() {
        if (p)
            elpis_corpus_close(p);
    }
};

struct GraphGuard {
    elpis_context_graph *p = nullptr;
    ~GraphGuard() {
        if (p)
            elpis_context_graph_destroy(p);
    }
};

struct ResultGuard {
    elpis_regex_hacf_query_ingress_result_v1 *p = nullptr;
    ~ResultGuard() {
        if (p)
            elpis_regex_hacf_query_ingress_result_destroy_v1(p);
    }
};

static std::string checked(const char *p) {
    req(p != nullptr, "unexpected null string accessor");
    return std::string(p);
}

static void append_field(
    std::string &out,
    const char *name,
    const char *value)
{
    req(value != nullptr, "null identity field");
    out += name;
    out.push_back('=');
    out += value;
    out.push_back('\n');
}

static void append_candidates(
    std::string &out,
    const elpis_regex_hacf_query_ingress_result_v1 *r,
    bool require_nonempty)
{
    const uint32_t n =
        elpis_regex_hacf_query_ingress_result_candidate_count_v1(r);

    if (require_nonempty)
        req(n > 0u, "positive Regex result produced zero candidates");

    out += "candidate_count=";
    out += std::to_string(n);
    out.push_back('\n');

    for (uint32_t i = 0; i < n; ++i) {
        elpis_regex_hacf_query_ingress_candidate_view_v1 row{};

        req(
            elpis_regex_hacf_query_ingress_result_candidate_at_v1(
                r, i, &row) ==
                ELPIS_REGEX_HACF_QUERY_INGRESS_OK,
            "candidate accessor failed");

        out += "candidate_";
        out += std::to_string(i);
        out.push_back('=');
        out += row.candidate_id;
        out.push_back('\n');
    }
}

static std::string positive_identity(
    const std::string &task,
    size_t chunk,
    elpis_corpus *corpus,
    elpis_context_graph *graph)
{
    ResultGuard r;

    const int rc =
        elpis_regex_hacf_query_ingress_run_v1(
            reinterpret_cast<const uint8_t *>(task.data()),
            task.size(),
            chunk,
            corpus,
            graph,
            &r.p);

    if (rc != ELPIS_REGEX_HACF_QUERY_INGRESS_OK) {
        std::cerr
            << "FAIL positive composite rc=" << rc
            << " chunk=" << chunk
            << " error="
            << elpis_regex_hacf_query_ingress_last_error_v1()
            << "\n";
        std::exit(1);
    }

    req(r.p != nullptr, "positive composite returned null");

    req(
        elpis_regex_hacf_query_ingress_result_fail_closed_v1(r.p) == 0,
        "positive composite unexpectedly fail-closed");

    req(
        elpis_regex_hacf_query_ingress_result_batch_published_v1(r.p) == 1,
        "positive composite did not publish atomic batch");

    req(
        checked(
            elpis_regex_hacf_query_ingress_result_status_v1(r.p)) ==
            "PUBLISHED_ATOMIC_QUERY_OVERLAY",
        "unexpected positive composite status");

    req(
        elpis_regex_hacf_query_ingress_result_semantic_authority_v1(r.p) == 0,
        "semantic authority became nonzero");

    req(
        elpis_regex_hacf_query_ingress_result_admission_authority_v1(r.p) == 0,
        "admission authority became nonzero");

    req(
        elpis_regex_hacf_query_ingress_result_execution_authority_v1(r.p) == 0,
        "execution authority became nonzero");

    req(
        elpis_regex_hacf_query_ingress_result_runtime_admission_v1(r.p) == 0,
        "runtime admission became nonzero");

    std::string out;

    append_field(
        out,
        "source_sha256",
        elpis_regex_hacf_query_ingress_result_source_sha256_v1(r.p));

    append_field(
        out,
        "proposal_digest",
        elpis_regex_hacf_query_ingress_result_proposal_digest_v1(r.p));

    append_field(
        out,
        "corpus_manifest_digest",
        elpis_regex_hacf_query_ingress_result_corpus_manifest_digest_v1(r.p));

    append_field(
        out,
        "context_graph_manifest_digest",
        elpis_regex_hacf_query_ingress_result_context_graph_manifest_digest_v1(r.p));

    append_field(
        out,
        "proposal_set_digest",
        elpis_regex_hacf_query_ingress_result_proposal_set_digest_v1(r.p));

    append_field(
        out,
        "query_local_segment_digest",
        elpis_regex_hacf_query_ingress_result_query_local_segment_digest_v1(r.p));

    append_field(
        out,
        "overlay_identity",
        elpis_regex_hacf_query_ingress_result_overlay_identity_v1(r.p));

    append_field(
        out,
        "batch_receipt_identity",
        elpis_regex_hacf_query_ingress_result_batch_receipt_identity_v1(r.p));

    append_candidates(out, r.p, true);

    return out;
}

static std::string contradiction_identity(
    const std::string &task,
    size_t chunk,
    elpis_corpus *corpus,
    elpis_context_graph *graph)
{
    ResultGuard r;

    const int rc =
        elpis_regex_hacf_query_ingress_run_v1(
            reinterpret_cast<const uint8_t *>(task.data()),
            task.size(),
            chunk,
            corpus,
            graph,
            &r.p);

    if (rc != ELPIS_REGEX_HACF_QUERY_INGRESS_OK) {
        std::cerr
            << "FAIL contradiction composite rc=" << rc
            << " chunk=" << chunk
            << " error="
            << elpis_regex_hacf_query_ingress_last_error_v1()
            << "\n";
        std::exit(1);
    }

    req(r.p != nullptr, "contradiction returned null result");

    req(
        elpis_regex_hacf_query_ingress_result_fail_closed_v1(r.p) == 1,
        "contradiction did not fail closed");

    req(
        elpis_regex_hacf_query_ingress_result_batch_published_v1(r.p) == 0,
        "contradiction published a batch");

    req(
        checked(
            elpis_regex_hacf_query_ingress_result_status_v1(r.p)) ==
            "REJECTED_PRE_BATCH_AMBIGUITY",
        "unexpected contradiction status");

    std::string out;

    append_field(
        out,
        "source_sha256",
        elpis_regex_hacf_query_ingress_result_source_sha256_v1(r.p));

    append_field(
        out,
        "proposal_digest",
        elpis_regex_hacf_query_ingress_result_proposal_digest_v1(r.p));

    append_field(
        out,
        "corpus_manifest_digest",
        elpis_regex_hacf_query_ingress_result_corpus_manifest_digest_v1(r.p));

    append_field(
        out,
        "context_graph_manifest_digest",
        elpis_regex_hacf_query_ingress_result_context_graph_manifest_digest_v1(r.p));

    append_candidates(out, r.p, false);

    return out;
}

static void oversized_rejection(
    const std::string &task,
    size_t chunk,
    elpis_corpus *corpus,
    elpis_context_graph *graph)
{
    elpis_regex_hacf_query_ingress_result_v1 *r =
        reinterpret_cast<elpis_regex_hacf_query_ingress_result_v1 *>(0x1);

    const int rc =
        elpis_regex_hacf_query_ingress_run_v1(
            reinterpret_cast<const uint8_t *>(task.data()),
            task.size(),
            chunk,
            corpus,
            graph,
            &r);

    if (rc != ELPIS_REGEX_HACF_QUERY_INGRESS_E_REGEX) {
        std::cerr
            << "FAIL oversized composite rc=" << rc
            << " chunk=" << chunk
            << " error="
            << elpis_regex_hacf_query_ingress_last_error_v1()
            << "\n";
        std::exit(1);
    }

    req(r == nullptr, "oversized composite published a result");

    const char *err =
        elpis_regex_hacf_query_ingress_last_error_v1();

    req(err != nullptr, "oversized composite has null error");

    req(
        std::strcmp(
            err,
            "REGEX_ABI:-4:INPUT_EXCEEDS_CARRY") == 0,
        "unexpected oversized composite error");
}

int main(int argc, char **argv) {
    req(
        argc == 2,
        "usage: elpis_regex_hacf_b01_regression STATE_ROOT");

    const std::vector<size_t> chunks =
        {1, 2, 3, 7, 13, 64, 4096};

    CorpusGuard corpus;

    req(
        elpis_corpus_open(argv[1], &corpus.p) == 0,
        "failed to open qualification corpus");

    req(corpus.p != nullptr, "corpus returned null");

    GraphGuard graph;

    req(
        elpis_context_graph_create(
            nullptr, 0u, &graph.p) == 0,
        "failed to create empty context graph");

    req(graph.p != nullptr, "context graph returned null");

    uint64_t docs_before = 999u;
    uint64_t corpus_chunks_before = 999u;

    req(
        elpis_corpus_counts(
            corpus.p,
            &docs_before,
            &corpus_chunks_before) == 0,
        "initial corpus counts failed");

    req(
        docs_before == 0u &&
        corpus_chunks_before == 0u,
        "qualification corpus unexpectedly nonempty");

    req(
        elpis_context_graph_edge_count(graph.p) == 0u,
        "qualification graph unexpectedly nonempty");

    /*
     * These are successor mechanical fixtures, not reconstructed historical
     * R0 oracle fixtures.
     */
    const std::string positive =
        "touching endpoints may merge; maximum end.";

    const std::string contradictory =
        "touching endpoints do not merge; "
        "touching endpoints may merge; maximum end.";

    const std::string astra =
        std::string("touching endpoints do not merge.") +
        std::string(1100, ' ') +
        "touching endpoints may merge; maximum end.";

    req(astra.size() == 1174u, "Astra fixture length changed");

    std::string positive_baseline;
    std::string contradiction_baseline;

    for (size_t chunk : chunks) {
        const std::string p =
            positive_identity(
                positive,
                chunk,
                corpus.p,
                graph.p);

        if (positive_baseline.empty())
            positive_baseline = p;
        else
            req(
                p == positive_baseline,
                "positive full-chain identity is chunk-sensitive");

        const std::string c =
            contradiction_identity(
                contradictory,
                chunk,
                corpus.p,
                graph.p);

        if (contradiction_baseline.empty())
            contradiction_baseline = c;
        else
            req(
                c == contradiction_baseline,
                "contradiction full-chain identity is chunk-sensitive");

        oversized_rejection(
            astra,
            chunk,
            corpus.p,
            graph.p);
    }

    uint64_t docs_after = 999u;
    uint64_t corpus_chunks_after = 999u;

    req(
        elpis_corpus_counts(
            corpus.p,
            &docs_after,
            &corpus_chunks_after) == 0,
        "final corpus counts failed");

    req(
        docs_after == docs_before &&
        corpus_chunks_after == corpus_chunks_before,
        "composite mutated HACF corpus");

    req(
        elpis_context_graph_edge_count(graph.p) == 0u,
        "composite mutated context graph");

    std::cout
        << "positive_identity_begin\n"
        << positive_baseline
        << "positive_identity_end\n"
        << "contradiction_identity_begin\n"
        << contradiction_baseline
        << "contradiction_identity_end\n"
        << "oversized_default_profile=REJECTED_PRE_HACF\n"
        << "oversized_result_published=false\n"
        << "oversized_batch_published=false\n"
        << "semantic_authority=false\n"
        << "admission_authority=false\n"
        << "execution_authority=false\n"
        << "runtime_admission=false\n"
        << "PASS_REGEX_HACF_B01_PREPUBLICATION_R1\n";

    return 0;
}
