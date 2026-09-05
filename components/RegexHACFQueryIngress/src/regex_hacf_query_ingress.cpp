#include "regex_hacf_query_ingress.h"

#include "streaming_regex_ingress.h"
#include "query_local_proposal_batch.h"
#include "canonical_json.hpp"
#include "elpis/sha256.h"

#include <charconv>
#include <cmath>
#include <cstring>
#include <new>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace detail = elpis::regex_hacf_query_ingress::detail;

static const char *REGISTRY_CONTRACT_HEX =
    "9ac8ec7d88cad77f998e2552b4b72fb16042432025966d9abff6cca551bc5468";
static const char *NATIVE_REGISTRY_HEX =
    "d2012aad35f795b9d798e5a3f0aeb685a4ac0ffafd9df71f6950ed0e35d87f15";
static const char *POLICY_HEX =
    "8230edd0f653f9b55325766eb88f36ecda0c8c3573af74433dd3bd435e078bcd";

struct elpis_regex_hacf_query_ingress_result_v1 {
    std::string status;
    std::string source_sha256;
    std::string proposal_digest;
    std::string corpus_manifest_digest;
    std::string context_graph_manifest_digest;
    std::string proposal_set_digest;
    std::string query_local_segment_digest;
    std::string overlay_identity;
    std::string batch_receipt_identity;
    std::string proposal_json;
    std::vector<std::string> candidate_ids;
    bool fail_closed=false;
    bool batch_published=false;
};

static thread_local std::string LAST_ERROR;

struct RegexGuard {
    elpis_streaming_regex_result_v1 *p=nullptr;
    ~RegexGuard(){ if(p) elpis_streaming_regex_result_destroy_v1(p); }
};

struct OverlayGuard {
    semantic_query_overlay *p=nullptr;
    ~OverlayGuard(){ if(p) semantic_overlay_destroy(p); }
};

struct RegistryGuard {
    semantic_type_registry *p=nullptr;
    ~RegistryGuard(){ if(p) semantic_type_registry_destroy(p); }
};

struct RegexEvidence {
    std::string evidence_id;
    std::string pattern_id;
    std::string lexical_anchor;
};

struct RegexView {
    std::string source_sha256;
    std::string ingress_json;
    std::string composition_json;
    std::vector<RegexEvidence> evidence;
    std::vector<std::string> candidate_ids;
    bool fail_closed=false;
};

static std::string cstr65(const char v[65]) {
    return std::string(v,strnlen(v,65));
}
static std::string cstr96(const char v[96]) {
    return std::string(v,strnlen(v,96));
}
static std::string cstr32(const char v[32]) {
    return std::string(v,strnlen(v,32));
}

static hacf_digest hex_to_digest(const std::string &h) {
    if(h.size()!=64) throw std::runtime_error("HEX_DIGEST_LENGTH");
    hacf_digest d{};
    auto nyb=[](char c)->int{
        if(c>='0'&&c<='9') return c-'0';
        if(c>='a'&&c<='f') return c-'a'+10;
        if(c>='A'&&c<='F') return c-'A'+10;
        return -1;
    };
    for(size_t i=0;i<32;++i){
        int a=nyb(h[2*i]),b=nyb(h[2*i+1]);
        if(a<0||b<0) throw std::runtime_error("HEX_DIGEST_CHAR");
        d.bytes[i]=(uint8_t)((a<<4)|b);
    }
    return d;
}

static bool digest_eq(const hacf_digest &a,const hacf_digest &b) {
    return memcmp(a.bytes,b.bytes,HACF_DIGEST_BYTES)==0;
}

static std::string digest_hex(const hacf_digest &d) {
    return detail::hex_digest(d.bytes);
}

static std::string py_float(double v) {
    if(!std::isfinite(v)) throw std::runtime_error("NONFINITE_HACF_SCORE");
    char buf[128];
    auto r=std::to_chars(buf,buf+sizeof(buf),v,std::chars_format::general);
    if(r.ec!=std::errc()) throw std::runtime_error("FLOAT_FORMAT");
    std::string s(buf,r.ptr);
    if(s.find_first_of(".eE")==std::string::npos) s += ".0";
    return s;
}

static std::string corpus_manifest_digest(elpis_corpus *corpus) {
    char *json=nullptr;
    char digest[65]={0};
    int rc=elpis_corpus_manifest_json(corpus,&json,digest);
    if(rc!=0 || !json) throw std::runtime_error("HACF_CORPUS_MANIFEST");
    elpis_free(json);
    return cstr65(digest);
}

static std::string graph_manifest_digest(elpis_context_graph *graph) {
    char *json=nullptr;
    char digest[65]={0};
    int rc=elpis_context_graph_manifest_json(graph,&json,digest);
    if(rc!=0 || !json) throw std::runtime_error("HACF_GRAPH_MANIFEST");
    elpis_free(json);
    return cstr65(digest);
}

static std::string chunk_text(elpis_corpus *corpus,const std::string &digest) {
    char *text=nullptr;
    if(elpis_corpus_chunk_text(corpus,digest.c_str(),&text)!=0 || !text)
        throw std::runtime_error("HACF_CHUNK_TEXT");
    std::string out(text);
    elpis_free(text);
    return out;
}

static RegexView read_regex_view(
    const uint8_t *task_bytes,
    size_t task_len,
    size_t chunk_size)
{
    RegexGuard guard;
    int rc=elpis_streaming_regex_parse_bytes_v1(
        task_bytes,
        task_len,
        chunk_size,
        ELPIS_STREAMING_REGEX_DEFAULT_CARRY_BYTES_V1,
        &guard.p);

    if(rc!=ELPIS_STREAMING_REGEX_OK || !guard.p) {
        const char *detail_msg=elpis_streaming_regex_last_error_v1();
        throw std::runtime_error(
            std::string("REGEX_ABI:")+std::to_string(rc)+":"+
            (detail_msg?detail_msg:""));
    }

    const char *source=
        elpis_streaming_regex_result_source_sha256_v1(guard.p);
    const char *ingress=
        elpis_streaming_regex_result_ingress_json_v1(guard.p);
    const char *composition=
        elpis_streaming_regex_result_composition_json_v1(guard.p);
    if(!source || !ingress || !composition)
        throw std::runtime_error("REGEX_ABI_NULL_VIEW");

    RegexView view;
    view.source_sha256=source;
    view.ingress_json=ingress;
    view.composition_json=composition;
    view.fail_closed=
        elpis_streaming_regex_result_fail_closed_v1(guard.p)!=0;

    uint32_t ne=elpis_streaming_regex_result_evidence_count_v1(guard.p);
    view.evidence.reserve(ne);
    for(uint32_t i=0;i<ne;++i) {
        elpis_streaming_regex_evidence_view_v1 row{};
        rc=elpis_streaming_regex_result_evidence_at_v1(guard.p,i,&row);
        if(rc!=ELPIS_STREAMING_REGEX_OK ||
           row.abi_version!=ELPIS_STREAMING_REGEX_ABI_VERSION_V1)
            throw std::runtime_error("REGEX_ABI_EVIDENCE");
        view.evidence.push_back({
            std::string(row.evidence_id),
            std::string(row.pattern_id),
            std::string(row.lexical_anchor)
        });
    }

    uint32_t nc=elpis_streaming_regex_result_candidate_count_v1(guard.p);
    view.candidate_ids.reserve(nc);
    for(uint32_t i=0;i<nc;++i) {
        elpis_streaming_regex_candidate_view_v1 row{};
        rc=elpis_streaming_regex_result_candidate_at_v1(guard.p,i,&row);
        if(rc!=ELPIS_STREAMING_REGEX_OK ||
           row.abi_version!=ELPIS_STREAMING_REGEX_ABI_VERSION_V1)
            throw std::runtime_error("REGEX_ABI_CANDIDATE");
        view.candidate_ids.push_back(std::string(row.candidate_id));
    }

    return view;
}

static detail::J build_context_proposal(
    elpis_corpus *corpus,
    elpis_context_graph *graph,
    const RegexView &regex)
{
    detail::J::A retrieval;

    for(const auto &ev:regex.evidence) {
        std::vector<elpis_hit> hits(16);
        uint32_t nh=0;
        if(elpis_corpus_search_lexical(
            corpus,
            ev.lexical_anchor.c_str(),
            nullptr,
            nullptr,
            16,
            hits.data(),
            &nh)!=0)
            throw std::runtime_error("HACF_LEXICAL");

        detail::J::A hit_rows;
        for(uint32_t i=0;i<nh;++i) {
            const auto &h=hits[i];
            std::string chunk=cstr65(h.chunk_digest);
            std::string text=chunk_text(corpus,chunk);

            std::vector<elpis_context_neighbor> neighbors(16);
            uint32_t nn=0;
            if(elpis_context_graph_neighbors(
                graph,
                chunk.c_str(),
                0,
                0,
                16,
                neighbors.data(),
                &nn)!=0)
                throw std::runtime_error("HACF_NEIGHBORS");

            detail::J::A context;
            for(uint32_t k=0;k<nn;++k) {
                const auto &n=neighbors[k];
                std::string nd=cstr65(n.chunk_digest);

                detail::J::O no;
                no["authority"]=detail::J::num(std::to_string(n.authority));
                no["chunk_digest"]=nd;
                no["edge_type"]=detail::J::num(std::to_string(n.edge_type));
                no["provenance_digest"]=cstr65(n.provenance_digest);
                no["text"]=chunk_text(corpus,nd);
                context.push_back(detail::J(std::move(no)));
            }

            detail::J::O ho;
            ho["authority"]=cstr32(h.authority);
            ho["byte_end"]=detail::J::num(std::to_string(h.byte_end));
            ho["byte_start"]=detail::J::num(std::to_string(h.byte_start));
            ho["chunk_digest"]=chunk;
            ho["context_neighbors"]=detail::J(std::move(context));
            ho["doc_digest"]=cstr65(h.doc_digest);
            ho["lexical_score"]=detail::J::num(py_float(h.lexical_score));
            ho["namespace"]=cstr96(h.ns);
            ho["ordinal"]=detail::J::num(std::to_string(h.ordinal));
            ho["text"]=text;
            ho["text_sha256"]=detail::sha_string(text);
            hit_rows.push_back(detail::J(std::move(ho)));
        }

        detail::J::O rr;
        rr["evidence_id"]=ev.evidence_id;
        rr["hacf_primary_hits"]=detail::J(std::move(hit_rows));
        rr["lexical_anchor"]=ev.lexical_anchor;
        rr["pattern_id"]=ev.pattern_id;
        retrieval.push_back(detail::J(std::move(rr)));
    }

    std::string corpus_digest=corpus_manifest_digest(corpus);
    std::string graph_digest=graph_manifest_digest(graph);

    detail::J::O hacf;
    hacf["component"]="HACF_R3";
    hacf["context_graph_manifest_digest"]=graph_digest;
    hacf["corpus_manifest_digest"]=corpus_digest;
    hacf["dense_vector_used"]=false;
    hacf["hybrid_retriever_used"]=false;
    hacf["mode"]="native_lexical_corpus_plus_context_graph";
    hacf["retrieval"]=detail::J(std::move(retrieval));
    hacf["retrieval_bundle_claimed"]=false;

    detail::J::O proposal;
    proposal["admission_authority"]=false;
    proposal["candidate_status"]="PROPOSED_UNADMITTED";
    proposal["execution_authority"]=false;
    proposal["grid81_mapping"]=detail::J(nullptr);
    proposal["hacf"]=detail::J(std::move(hacf));
    proposal["regex_ingress"]=detail::J::raw(regex.ingress_json);
    proposal["runtime_admission"]=false;
    proposal["schema"]="elpis.regex-hacf-context-proposal.r1";
    proposal["semantic_authority"]=false;
    proposal["source_sha256"]=regex.source_sha256;
    proposal["task_composition"]=detail::J::raw(regex.composition_json);

    std::string pd=detail::sha_json(detail::J(proposal));
    proposal["proposal_digest"]=pd;
    return detail::J(std::move(proposal));
}

static void base_manifest_digest(
    const hacf_digest &corpus,
    const hacf_digest &graph,
    hacf_digest &out)
{
    static const char domain[]=
        "elpis.live.regex-hacf.query-local.batch.r0.base";
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    elpis_sha256_update(&ctx,domain,sizeof(domain)-1u);
    elpis_sha256_update(&ctx,corpus.bytes,HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx,graph.bytes,HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx,out.bytes);
}

static void publish_batch(
    const detail::J &proposal,
    const RegexView &regex,
    elpis_regex_hacf_query_ingress_result_v1 &result)
{
    const auto &po=proposal.obj();

    result.status="REJECTED_PRE_BATCH_AMBIGUITY";
    result.source_sha256=regex.source_sha256;
    result.proposal_digest=
        std::get<std::string>(po.at("proposal_digest").v);
    result.corpus_manifest_digest=
        std::get<std::string>(
            po.at("hacf").obj().at("corpus_manifest_digest").v);
    result.context_graph_manifest_digest=
        std::get<std::string>(
            po.at("hacf").obj().at("context_graph_manifest_digest").v);
    result.proposal_json=detail::dump(proposal);
    result.candidate_ids=regex.candidate_ids;
    result.fail_closed=regex.fail_closed;
    result.batch_published=false;

    if(regex.fail_closed)
        return;

    if(regex.candidate_ids.empty())
        throw std::runtime_error("ZERO_CANDIDATES");

    RegistryGuard registry;
    registry.p=semantic_type_registry_create();
    if(!registry.p)
        throw std::bad_alloc();

    semantic_node_type_entry node_type{};
    node_type.node_type=ELPIS_QUERY_LOCAL_PROPOSAL_NODE_TYPE;
    node_type.semantic_flag_mask=SEMANTIC_NODE_FLAG_EXTERNAL;
    node_type.min_authority=0;
    node_type.max_authority=0;
    if(semantic_type_registry_add_node_type(
        registry.p,&node_type)!=SEMANTIC_OK)
        throw std::runtime_error("REGISTRY_ADD_TYPE");

    hacf_digest native_registry{};
    if(semantic_type_registry_seal(
        registry.p,&native_registry)!=SEMANTIC_OK)
        throw std::runtime_error("REGISTRY_SEAL");

    if(!digest_eq(native_registry,hex_to_digest(NATIVE_REGISTRY_HEX)))
        throw std::runtime_error("NATIVE_REGISTRY_DIGEST_DRIFT");

    elpis_query_local_context_v1 context{};
    context.query_digest=
        hex_to_digest(result.source_sha256);
    context.proposal_digest=
        hex_to_digest(result.proposal_digest);
    context.hacf_corpus_manifest_digest=
        hex_to_digest(result.corpus_manifest_digest);
    context.hacf_context_graph_manifest_digest=
        hex_to_digest(result.context_graph_manifest_digest);
    context.registry_contract_digest=
        hex_to_digest(REGISTRY_CONTRACT_HEX);
    context.native_registry_digest=native_registry;
    context.representation_policy_digest=
        hex_to_digest(POLICY_HEX);

    std::vector<elpis_query_local_proposal_v1> props(
        regex.candidate_ids.size());

    for(size_t i=0;i<regex.candidate_ids.size();++i) {
        auto &p=props[i];
        memset(&p,0,sizeof p);
        p.abi_version=ELPIS_QUERY_LOCAL_PROPOSAL_ABI_VERSION;
        p.query_digest=context.query_digest;
        p.proposal_digest=context.proposal_digest;
        p.candidate_digest=
            hex_to_digest(regex.candidate_ids[i]);
        p.hacf_corpus_manifest_digest=
            context.hacf_corpus_manifest_digest;
        p.hacf_context_graph_manifest_digest=
            context.hacf_context_graph_manifest_digest;
        p.registry_contract_digest=
            context.registry_contract_digest;
        p.native_registry_digest=
            context.native_registry_digest;
        p.representation_policy_digest=
            context.representation_policy_digest;
        p.candidate_status=
            ELPIS_QUERY_LOCAL_PROPOSAL_STATUS_PROPOSED_UNADMITTED;

        if(elpis_query_local_proposal_identity(
            &p,&p.envelope_identity)!=SEMANTIC_OK)
            throw std::runtime_error("PROPOSAL_IDENTITY");
    }

    semantic_snapshot_manifest base{};
    base.abi_version=SEMANTIC_SNAPSHOT_ABI_VERSION;
    base.hacf_graph_snapshot_digest=
        context.hacf_context_graph_manifest_digest;
    base_manifest_digest(
        context.hacf_corpus_manifest_digest,
        context.hacf_context_graph_manifest_digest,
        base.manifest_digest);

    OverlayGuard overlay;
    elpis_query_local_proposal_batch_receipt_v1 receipt{};

    int rc=elpis_query_local_proposal_batch_build_overlay(
        &base,
        registry.p,
        &context,
        props.data(),
        (uint32_t)props.size(),
        &overlay.p,
        &receipt);

    if(rc!=SEMANTIC_OK || !overlay.p)
        throw std::runtime_error(
            std::string("BATCH_BUILD:")+std::to_string(rc));

    result.proposal_set_digest=
        digest_hex(receipt.proposal_set_digest);
    result.query_local_segment_digest=
        digest_hex(overlay.p->query_local_segment_digest);
    result.overlay_identity=
        digest_hex(overlay.p->overlay_identity);
    result.batch_receipt_identity=
        digest_hex(receipt.receipt_identity);
    result.status="PUBLISHED_ATOMIC_QUERY_OVERLAY";
    result.batch_published=true;
}

static bool copy_cstr(char *dst,size_t cap,const std::string &src) {
    if(!dst || cap==0 || src.size()+1>cap)
        return false;
    memset(dst,0,cap);
    memcpy(dst,src.data(),src.size());
    return true;
}

extern "C"
uint32_t elpis_regex_hacf_query_ingress_abi_version_v1(void) {
    return ELPIS_REGEX_HACF_QUERY_INGRESS_ABI_VERSION_V1;
}

extern "C"
int elpis_regex_hacf_query_ingress_run_v1(
    const uint8_t *task_bytes,
    size_t task_len,
    size_t regex_chunk_size,
    elpis_corpus *corpus,
    elpis_context_graph *context_graph,
    elpis_regex_hacf_query_ingress_result_v1 **out)
{
    if(!out)
        return ELPIS_REGEX_HACF_QUERY_INGRESS_E_INVAL;
    *out=nullptr;
    LAST_ERROR.clear();

    if((task_len && !task_bytes) ||
       regex_chunk_size==0 ||
       !corpus ||
       !context_graph)
        return ELPIS_REGEX_HACF_QUERY_INGRESS_E_INVAL;

    try {
        RegexView regex=
            read_regex_view(task_bytes,task_len,regex_chunk_size);

        detail::J proposal=
            build_context_proposal(corpus,context_graph,regex);

        auto *result=
            new elpis_regex_hacf_query_ingress_result_v1;

        try {
            publish_batch(proposal,regex,*result);
        } catch(...) {
            delete result;
            throw;
        }

        *out=result;
        return ELPIS_REGEX_HACF_QUERY_INGRESS_OK;
    } catch(const std::bad_alloc &) {
        LAST_ERROR="NOMEM";
        return ELPIS_REGEX_HACF_QUERY_INGRESS_E_NOMEM;
    } catch(const std::exception &e) {
        LAST_ERROR=e.what();
        if(LAST_ERROR.rfind("REGEX_ABI:",0)==0)
            return ELPIS_REGEX_HACF_QUERY_INGRESS_E_REGEX;
        if(LAST_ERROR.rfind("HACF_",0)==0)
            return ELPIS_REGEX_HACF_QUERY_INGRESS_E_HACF;
        if(LAST_ERROR=="ZERO_CANDIDATES")
            return ELPIS_REGEX_HACF_QUERY_INGRESS_E_CARDINALITY;
        return ELPIS_REGEX_HACF_QUERY_INGRESS_E_BATCH;
    } catch(...) {
        LAST_ERROR="UNKNOWN";
        return ELPIS_REGEX_HACF_QUERY_INGRESS_E_BATCH;
    }
}

extern "C"
void elpis_regex_hacf_query_ingress_result_destroy_v1(
    elpis_regex_hacf_query_ingress_result_v1 *result)
{
    delete result;
}

#define STR_ACCESSOR(name,field) \
extern "C" \
const char *name( \
    const elpis_regex_hacf_query_ingress_result_v1 *result) \
{ \
    return result ? result->field.c_str() : nullptr; \
}

STR_ACCESSOR(
    elpis_regex_hacf_query_ingress_result_status_v1,
    status)
STR_ACCESSOR(
    elpis_regex_hacf_query_ingress_result_source_sha256_v1,
    source_sha256)
STR_ACCESSOR(
    elpis_regex_hacf_query_ingress_result_proposal_digest_v1,
    proposal_digest)
STR_ACCESSOR(
    elpis_regex_hacf_query_ingress_result_corpus_manifest_digest_v1,
    corpus_manifest_digest)
STR_ACCESSOR(
    elpis_regex_hacf_query_ingress_result_context_graph_manifest_digest_v1,
    context_graph_manifest_digest)
STR_ACCESSOR(
    elpis_regex_hacf_query_ingress_result_proposal_set_digest_v1,
    proposal_set_digest)
STR_ACCESSOR(
    elpis_regex_hacf_query_ingress_result_query_local_segment_digest_v1,
    query_local_segment_digest)
STR_ACCESSOR(
    elpis_regex_hacf_query_ingress_result_overlay_identity_v1,
    overlay_identity)
STR_ACCESSOR(
    elpis_regex_hacf_query_ingress_result_batch_receipt_identity_v1,
    batch_receipt_identity)
STR_ACCESSOR(
    elpis_regex_hacf_query_ingress_result_proposal_json_v1,
    proposal_json)

#undef STR_ACCESSOR

extern "C"
uint32_t elpis_regex_hacf_query_ingress_result_candidate_count_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result)
{
    return result ? (uint32_t)result->candidate_ids.size() : 0u;
}

extern "C"
int elpis_regex_hacf_query_ingress_result_candidate_at_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result,
    uint32_t index,
    elpis_regex_hacf_query_ingress_candidate_view_v1 *out)
{
    if(!result || !out)
        return ELPIS_REGEX_HACF_QUERY_INGRESS_E_INVAL;
    if(index>=result->candidate_ids.size())
        return ELPIS_REGEX_HACF_QUERY_INGRESS_E_RANGE;

    memset(out,0,sizeof *out);
    out->abi_version=
        ELPIS_REGEX_HACF_QUERY_INGRESS_ABI_VERSION_V1;
    if(!copy_cstr(
        out->candidate_id,
        sizeof out->candidate_id,
        result->candidate_ids[index]))
        return ELPIS_REGEX_HACF_QUERY_INGRESS_E_RANGE;

    return ELPIS_REGEX_HACF_QUERY_INGRESS_OK;
}

extern "C"
int elpis_regex_hacf_query_ingress_result_fail_closed_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result)
{
    return result && result->fail_closed ? 1 : 0;
}

extern "C"
int elpis_regex_hacf_query_ingress_result_batch_published_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result)
{
    return result && result->batch_published ? 1 : 0;
}

extern "C"
int elpis_regex_hacf_query_ingress_result_semantic_authority_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result)
{
    (void)result;
    return 0;
}

extern "C"
int elpis_regex_hacf_query_ingress_result_admission_authority_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result)
{
    (void)result;
    return 0;
}

extern "C"
int elpis_regex_hacf_query_ingress_result_execution_authority_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result)
{
    (void)result;
    return 0;
}

extern "C"
int elpis_regex_hacf_query_ingress_result_runtime_admission_v1(
    const elpis_regex_hacf_query_ingress_result_v1 *result)
{
    (void)result;
    return 0;
}

extern "C"
const char *elpis_regex_hacf_query_ingress_last_error_v1(void) {
    return LAST_ERROR.c_str();
}
