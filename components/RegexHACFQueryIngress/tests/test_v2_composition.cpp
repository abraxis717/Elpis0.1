#include "regex_hacf_query_ingress_v2.h"
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
static void req(bool b,const char* why) {
    if(!b) { std::cerr<<why<<": "<<elpis_regex_hacf_query_ingress_last_error_v1()<<"\n"; std::exit(1); }
}
static std::string identity(const elpis_regex_hacf_query_ingress_result_v1* r) {
    std::string out;
    for(const char* s:{elpis_regex_hacf_query_ingress_result_proposal_json_v1(r),
        elpis_regex_hacf_query_ingress_result_proposal_digest_v1(r),
        elpis_regex_hacf_query_ingress_result_proposal_set_digest_v1(r),
        elpis_regex_hacf_query_ingress_result_query_local_segment_digest_v1(r),
        elpis_regex_hacf_query_ingress_result_overlay_identity_v1(r),
        elpis_regex_hacf_query_ingress_result_batch_receipt_identity_v1(r),
        elpis_regex_hacf_query_ingress_result_status_v1(r)}) { req(s,"null identity"); out+=s; out+='\n'; }
    req(!elpis_regex_hacf_query_ingress_result_semantic_authority_v1(r),"semantic authority");
    req(!elpis_regex_hacf_query_ingress_result_admission_authority_v1(r),"admission authority");
    req(!elpis_regex_hacf_query_ingress_result_execution_authority_v1(r),"execution authority");
    req(!elpis_regex_hacf_query_ingress_result_runtime_admission_v1(r),"runtime authority");
    return out;
}
int main(int argc,char** argv) {
    req(argc==2,"state root required");
    elpis_corpus* corpus=nullptr; elpis_context_graph* graph=nullptr;
    req(elpis_corpus_open(argv[1],&corpus)==0,"corpus");
    req(elpis_context_graph_create(nullptr,0,&graph)==0,"graph");
    elpis_regex_hacf_query_ingress_result_v1* out=nullptr;
    req(elpis_regex_hacf_query_ingress_from_regex_result_v2(nullptr,corpus,graph,&out)==-1 && !out,"null Regex result");
    for(const std::string& text:{std::string("touching endpoints may merge; maximum end."),
                               std::string("touching endpoints do not merge; touching endpoints may merge; maximum end.")}) {
        elpis_regex_hacf_query_ingress_result_v1* old=nullptr;
        req(elpis_regex_hacf_query_ingress_run_v1(reinterpret_cast<const uint8_t*>(text.data()),text.size(),7,corpus,graph,&old)==0,"old composition");
        const std::string expected=identity(old);
        for(size_t chunk:{1u,2u,7u,4096u}) {
            elpis_streaming_regex_stream_v2* s=nullptr; elpis_streaming_regex_result_v1* regex=nullptr;
            req(elpis_streaming_regex_stream_create_v2(nullptr,&s)==0,"create");
            for(size_t i=0;i<text.size();i+=chunk)
                req(elpis_streaming_regex_stream_feed_v2(s,reinterpret_cast<const uint8_t*>(text.data()+i),std::min(chunk,text.size()-i))==0,"feed");
            req(elpis_streaming_regex_stream_finalize_v2(s,&regex)==0,"finalize");
            elpis_streaming_regex_stream_destroy_v2(s); // result lifetime is independent.
            req(elpis_regex_hacf_query_ingress_from_regex_result_v2(regex,corpus,graph,&out)==0,"V2 composition");
            req(identity(out)==expected,"complete composition identity parity");
            req(elpis_regex_hacf_query_ingress_result_batch_published_v1(out)==elpis_regex_hacf_query_ingress_result_batch_published_v1(old),"batch parity");
            elpis_regex_hacf_query_ingress_result_destroy_v1(out); out=nullptr;
            elpis_streaming_regex_result_destroy_v1(regex);
        }
        elpis_regex_hacf_query_ingress_result_destroy_v1(old);
    }
    // Multi-megabyte source reaches the same authority-zero composition boundary.
    for(bool ambiguous:{false,true}) {
        elpis_streaming_regex_stream_v2* s=nullptr; elpis_streaming_regex_result_v1* regex=nullptr;
        req(elpis_streaming_regex_stream_create_v2(nullptr,&s)==0,"long create");
        std::string block(65536,'z');
        for(int i=0;i<40;++i) req(elpis_streaming_regex_stream_feed_v2(s,reinterpret_cast<const uint8_t*>(block.data()),block.size())==0,"long feed");
        std::string end="; touching endpoints may merge; maximum end.";
        if(ambiguous) end+=" touching endpoints do not merge.";
        req(elpis_streaming_regex_stream_feed_v2(s,reinterpret_cast<const uint8_t*>(end.data()),end.size())==0,"late feed");
        req(elpis_streaming_regex_stream_finalize_v2(s,&regex)==0,"long finalize");
        req(elpis_regex_hacf_query_ingress_from_regex_result_v2(regex,corpus,graph,&out)==0,"long composition");
        identity(out);
        req(elpis_regex_hacf_query_ingress_result_batch_published_v1(out)==!ambiguous,"long ambiguity prepublication");
        elpis_regex_hacf_query_ingress_result_destroy_v1(out); out=nullptr;
        elpis_streaming_regex_result_destroy_v1(regex); elpis_streaming_regex_stream_destroy_v2(s);
    }
    uint64_t docs=1,chunks=1;
    req(elpis_corpus_counts(corpus,&docs,&chunks)==0 && docs==0 && chunks==0,"corpus mutation");
    req(elpis_context_graph_edge_count(graph)==0,"context mutation");
    elpis_context_graph_destroy(graph); elpis_corpus_close(corpus);
    std::cout<<"PASS_V2_COMPOSITION V1/V2 identity parity; long sources; no authority widening\n";
}
