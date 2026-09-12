#include "streaming_regex_ingress_v2.h"
#include "elpis/sha256.h"
#include <algorithm>
#include <array>
#include <cstdlib>
#include <dlfcn.h>
#include <cstring>
#include <iostream>
#include <random>
#include <string>
#include <vector>

static void require(bool b,const char* message) {
    if(!b) { std::cerr<<"FAIL "<<message<<" "<<elpis_streaming_regex_last_error_v2()<<"\n"; std::exit(1); }
}
struct Stream {
    elpis_streaming_regex_stream_v2* p=nullptr;
    explicit Stream(const elpis_streaming_regex_options_v2* o=nullptr) {
        require(elpis_streaming_regex_stream_create_v2(o,&p)==0,"create");
    }
    ~Stream() { elpis_streaming_regex_stream_destroy_v2(p); }
    int feed(const std::string& s) {
        return elpis_streaming_regex_stream_feed_v2(p,reinterpret_cast<const uint8_t*>(s.data()),s.size());
    }
};
struct Result {
    elpis_streaming_regex_result_v1* p=nullptr;
    ~Result() { elpis_streaming_regex_result_destroy_v1(p); }
    std::string json() const { return elpis_streaming_regex_result_json_v1(p); }
};
static std::string sha(const std::string& s) {
    uint8_t d[32]; char out[65]; elpis_sha256(s.data(),s.size(),d); elpis_hex32(d,out); return out;
}
static void views_equal(const Result& a,const Result& b) {
    require(a.json()==b.json(),"complete canonical JSON parity");
    require(std::strcmp(elpis_streaming_regex_result_ingress_json_v1(a.p),elpis_streaming_regex_result_ingress_json_v1(b.p))==0,"ingress parity");
    require(std::strcmp(elpis_streaming_regex_result_composition_json_v1(a.p),elpis_streaming_regex_result_composition_json_v1(b.p))==0,"composition parity");
    require(elpis_streaming_regex_result_source_bytes_v1(a.p)==elpis_streaming_regex_result_source_bytes_v1(b.p),"byte count parity");
    require(std::strcmp(elpis_streaming_regex_result_source_sha256_v1(a.p),elpis_streaming_regex_result_source_sha256_v1(b.p))==0,"source hash parity");
    require(elpis_streaming_regex_result_evidence_count_v1(a.p)==elpis_streaming_regex_result_evidence_count_v1(b.p),"evidence count parity");
    require(elpis_streaming_regex_result_candidate_count_v1(a.p)==elpis_streaming_regex_result_candidate_count_v1(b.p),"candidate count parity");
    require(elpis_streaming_regex_result_ambiguity_count_v1(a.p)==elpis_streaming_regex_result_ambiguity_count_v1(b.p),"ambiguity parity");
    require(elpis_streaming_regex_result_fail_closed_v1(a.p)==elpis_streaming_regex_result_fail_closed_v1(b.p),"disposition parity");
    for(uint32_t i=0;i<elpis_streaming_regex_result_evidence_count_v1(a.p);++i) {
        elpis_streaming_regex_evidence_view_v1 x{},y{};
        require(elpis_streaming_regex_result_evidence_at_v1(a.p,i,&x)==0,"evidence accessor");
        require(elpis_streaming_regex_result_evidence_at_v1(b.p,i,&y)==0,"evidence accessor");
        require(std::memcmp(&x,&y,sizeof(x))==0,"evidence ID/pattern/anchor parity");
    }
    for(uint32_t i=0;i<elpis_streaming_regex_result_candidate_count_v1(a.p);++i) {
        elpis_streaming_regex_candidate_view_v1 x{},y{};
        require(elpis_streaming_regex_result_candidate_at_v1(a.p,i,&x)==0,"candidate accessor");
        require(elpis_streaming_regex_result_candidate_at_v1(b.p,i,&y)==0,"candidate accessor");
        require(std::memcmp(&x,&y,sizeof(x))==0,"candidate ID parity");
    }
}
static uint64_t parity_runs=0;
static decltype(&elpis_streaming_regex_parse_bytes_v1) frozen_parse=nullptr;
static decltype(&elpis_streaming_regex_result_json_v1) frozen_json=nullptr;
static decltype(&elpis_streaming_regex_result_destroy_v1) frozen_destroy=nullptr;
static void parity(const std::string& source,const std::vector<size_t>& sizes) {
    Result v1;
    int expected=elpis_streaming_regex_parse_bytes_v1(reinterpret_cast<const uint8_t*>(source.data()),source.size(),source.size()+1,std::max(size_t(256),source.size()),&v1.p);
    if(frozen_parse) {
        elpis_streaming_regex_result_v1* original=nullptr;
        int rc=frozen_parse(reinterpret_cast<const uint8_t*>(source.data()),source.size(),source.size()+1,std::max(size_t(256),source.size()),&original);
        require(rc==expected,"frozen HEAD V1 acceptance");
        if(rc==0) require(v1.json()==frozen_json(original),"frozen HEAD V1 exact JSON");
        frozen_destroy(original);
    }
    Stream s;
    size_t offset=0;
    int rc=0;
    for(size_t n:sizes) {
        n=std::min(n,source.size()-offset);
        rc=elpis_streaming_regex_stream_feed_v2(s.p,reinterpret_cast<const uint8_t*>(source.data()+offset),n);
        offset+=n;
        if(rc) break;
    }
    if(!rc && offset<source.size()) rc=s.feed(source.substr(offset));
    Result v2;
    if(!rc) rc=elpis_streaming_regex_stream_finalize_v2(s.p,&v2.p);
    require((rc==0)==(expected==0),"V1/V2 acceptance parity");
    if(!rc) {
        if(v1.json()!=v2.json()) std::cerr<<"SOURCE "<<source<<"\nV1 "<<v1.json()<<"\nV2 "<<v2.json()<<"\n";
        views_equal(v1,v2);
        require(sha(source)==elpis_streaming_regex_result_source_sha256_v1(v2.p),"independent source hash");
    } else require(!v2.p,"failure publication");
    ++parity_runs;
}
static std::vector<std::string> fixtures() {
    return {
        "", "irrelevant prose", "at least 1", "no less than -2.5", "greater than or equal to +.25",
        "more than 1", "greater than 2", "strictly greater than 3", "above 4",
        "at most 5", "no greater than 6", "less than or equal to 7",
        "less than 8", "strictly less than 9", "below 10",
        "other than 1", "not equal to 2", "unequal to 3", "exactly equal to 4", "equal to 5", "exactly 6",
        "clamp x between lower and upper", "bound VALUE from LO through HI", "restrict a between b to c", "keep a from b and c",
        "x is the lower bound", "x as lower limit", "x is minimum", "x as floor",
        "x is the upper bound", "x as upper limit", "x is maximum", "x as ceiling",
        "touching endpoints do not merge", "touch boundaries does not merge", "endpoint contact don't merge",
        "touch endpoints these five other long words doesn't merge",
        "strict overlap", "strictly overlapping", "positive-width overlap", "positive width overlap", "interior overlap", "interiors overlap",
        "overlap or touch may merge", "overlapping or abutting ranges can also merge", "touch endpoints should merge", "abutting boundaries will merge",
        "maximum end", "max endpoint", "greatest ending coordinate", "farthest right edge", "farther end", "larger end",
        "minimum end", "min endpoint", "smallest ending coordinate", "nearest right edge", "nearer end", "lesser end",
        "touching endpoints do not merge; touching endpoints may merge; maximum end; minimum end",
        "at least 1; at least 1; exactly 2; x is floor; y is floor",
        "touch endpoints do not merge do not merge; touching endpoints do not merge",
        "at least +1.23456789012345678", "at least 1.2X", "at least 1.X", "at least 12345678901234567890123456789012345",
        "positive  width overlap; positive\twidth overlap", "at\n\t\r least\v\f-1.5",
        "\xcf\x80 at least 1 \xe2\x98\x83 \xf0\x9f\x98\x80",
        "at\xc2\xa0least\xe2\x80\x83+.5", "\xe2\x84\xaa is floor; \xc5\xbf is ceiling",
        "at least \xd9\xa1", // V1's UCP digit matches, but strtod rejects the payload.
        std::string("maximum end\0minimum end",23),
        std::string("at least ")+std::string(128,'x'),
        std::string("keep ")+std::string(128,'a')+" from "+std::string(128,'b')+" to "+std::string(128,'c')
    };
}
static void lifecycle() {
    require(elpis_streaming_regex_stream_create_v2(nullptr,nullptr)==-1,"null create output");
    elpis_streaming_regex_stream_destroy_v2(nullptr);
    require(elpis_streaming_regex_stream_feed_v2(nullptr,nullptr,0)==-1,"null feed stream");
    Result r;
    require(elpis_streaming_regex_stream_finalize_v2(nullptr,&r.p)==-1,"null finalize stream");
    require(!elpis_streaming_regex_result_json_v1(nullptr),"null accessor");
    Stream s;
    require(s.feed("")==0,"empty feed");
    require(elpis_streaming_regex_stream_feed_v2(s.p,nullptr,0)==0,"null zero feed");
    require(elpis_streaming_regex_stream_finalize_v2(s.p,nullptr)==-1,"null result slot");
    require(s.feed("exactly 1")==0,"feed after rejected output slot");
    require(!r.p,"no premature result");
    require(elpis_streaming_regex_stream_finalize_v2(s.p,&r.p)==0,"finalize");
    auto before=r.json(); Result twice;
    require(elpis_streaming_regex_stream_finalize_v2(s.p,&twice.p)==-5 && !twice.p,"double finalize");
    require(s.feed("exactly 2")==-5,"feed after finalize");
    require(r.json()==before,"published result immutable");
    Stream failed;
    require(elpis_streaming_regex_stream_feed_v2(failed.p,nullptr,1)==-1,"null nonzero");
    require(failed.feed("exactly 1")==-1,"feed after failure");
    require(elpis_streaming_regex_stream_finalize_v2(failed.p,&twice.p)==-1 && !twice.p,"finalize failure");
    elpis_streaming_regex_options_v2 o{2,sizeof(o),1,0,100};
    Stream limited(&o);
    require(limited.feed("exactly 1; exactly 2;")==-4,"evidence cap");
    require(elpis_streaming_regex_stream_finalize_v2(limited.p,&twice.p)==-4 && !twice.p,"evidence cap terminal");
    Stream exact(&o);
    require(exact.feed(std::string(99,'z'))==0 && exact.feed("z")==0,"exact source limit");
    require(exact.feed("z")==-4,"limit plus one");
    Stream bytes(&o);
    const uint8_t dummy=0;
    require(elpis_streaming_regex_stream_feed_v2(bytes.p,&dummy,SIZE_MAX)==-4,"overflow before dereference");
    for(int kind=0;kind<5;++kind) {
        auto bad=o;
        if(kind==0) bad.abi_version=1;
        if(kind==1) bad.struct_size=0;
        if(kind==2) bad.max_evidence=0;
        if(kind==3) bad.reserved=1;
        if(kind==4) bad.max_source_bytes=UINT64_MAX;
        elpis_streaming_regex_stream_v2* p=nullptr;
        require(elpis_streaming_regex_stream_create_v2(&bad,&p)==-1 && !p,"invalid options");
    }
    require(elpis_streaming_regex_stream_stats_v2(s.p,nullptr)==-1,"null stats");
}
static void invalid_utf8() {
    const std::vector<std::string> invalid={"\x80","\xc0\xaf","\xe0\x80\xaf","\xed\xa0\x80","\xf0\x80\x80\xaf","\xf4\x90\x80\x80","\xf5\x80\x80\x80","\xe2\x82","\xc2", "\xe2(","\xf0\x9f\x98"};
    for(const auto& bad:invalid) for(const auto& text:{bad+"exactly 1",std::string("exactly 1 ")+bad})
        for(size_t split=0;split<=text.size();++split) parity(text,{split});
    Stream s; require(s.feed(std::string(2*1024*1024,'z'))==0,"large valid prefix");
    require(s.feed("\x80 exactly 1")==-2,"late invalid UTF8"); Result r;
    require(elpis_streaming_regex_stream_finalize_v2(s.p,&r.p)==-2 && !r.p,"late invalid no publication");
}
static void long_stream() {
    const std::string block(65536,'z');
    Stream s; elpis_sha256_ctx h; elpis_sha256_init(&h);
    auto feed=[&](const std::string& v) { require(s.feed(v)==0,"long feed"); elpis_sha256_update(&h,v.data(),v.size()); };
    elpis_streaming_regex_stats_v2 early{},late{};
    for(size_t i=0;i<800;++i) { feed(block); if(i==15) elpis_streaming_regex_stream_stats_v2(s.p,&early); }
    elpis_streaming_regex_stream_stats_v2(s.p,&late);
    require(early.peak_inline_bytes==late.peak_inline_bytes && early.peak_capture_bytes==late.peak_capture_bytes && early.peak_threads==late.peak_threads,"50 MiB no-match state growth");
    feed("; exactly 1; ");
    for(size_t i=0;i<32;++i) feed(block);
    feed("; exactly 1; maximum end.");
    Result r; require(elpis_streaming_regex_stream_finalize_v2(s.p,&r.p)==0,"long finalize");
    uint8_t d[32]; char expected[65]; elpis_sha256_final(&h,d); elpis_hex32(d,expected);
    require(std::strcmp(expected,elpis_streaming_regex_result_source_sha256_v1(r.p))==0,"long source hash");
    require(elpis_streaming_regex_result_evidence_count_v1(r.p)==3,"distant evidence exactly once");
    // The same >50 MiB source also arrives in one caller-owned feed.
    std::string single(800*block.size(),'z'); single+="; exactly 1; ";
    single.append(32*block.size(),'z'); single+="; exactly 1; maximum end.";
    Stream one; require(one.feed(single)==0,"50 MiB single feed"); Result single_result;
    require(elpis_streaming_regex_stream_finalize_v2(one.p,&single_result.p)==0,"single-feed finalize");
    views_equal(r,single_result);
    std::cout<<"no_match_bytes="<<800*block.size()<<" peak_candidates="<<late.peak_candidates<<" peak_threads="<<late.peak_threads<<" inline_capacity="<<late.peak_inline_bytes<<" capture_capacity="<<late.peak_capture_bytes<<"\n";
    // Arbitrarily long mixed whitespace: hash the original match without keeping it.
    Stream ws; elpis_sha256_ctx match; elpis_sha256_init(&match);
    auto wf=[&](const std::string& v) { require(ws.feed(v)==0,"whitespace feed"); elpis_sha256_update(&match,v.data(),v.size()); };
    wf("at"); const std::string spaces=" \t\r\n\v\f";
    std::string run; for(size_t i=0;i<4096;++i) run+=spaces;
    for(size_t i=0;i<96;++i) wf(run);
    wf("least 1");
    Result wr; require(elpis_streaming_regex_stream_finalize_v2(ws.p,&wr.p)==0,"whitespace finalize");
    elpis_sha256_final(&match,d); elpis_hex32(d,expected);
    require(elpis_streaming_regex_result_evidence_count_v1(wr.p)==1,"long whitespace evidence");
    require(wr.json().find("\"matched_text_omitted\":true")!=std::string::npos,"explicit long evidence representation");
    require(wr.json().find(std::string("\"matched_text_sha256\":\"")+expected+"\"")!=std::string::npos,"long exact match hash");
    elpis_streaming_regex_stream_stats_v2(ws.p,&late);
    require(late.peak_inline_bytes<100000,"whitespace inline memory bound");
    std::cout<<"whitespace_bytes="<<96*run.size()+9<<" peak_candidates="<<late.peak_candidates<<" peak_threads="<<late.peak_threads<<" inline_capacity="<<late.peak_inline_bytes<<" capture_capacity="<<late.peak_capture_bytes<<" instructions="<<late.program_instructions<<"\n";
    Result rejected; const std::string over(1025,'z');
    require(elpis_streaming_regex_parse_bytes_v1(reinterpret_cast<const uint8_t*>(over.data()),over.size(),4096,1024,&rejected.p)==-4 && !rejected.p,"V1 range unchanged");
}
int main(int argc,char** argv) {
    void* oracle=nullptr;
    if(argc==2) {
        oracle=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
        require(oracle,"load frozen HEAD oracle");
        frozen_parse=reinterpret_cast<decltype(frozen_parse)>(dlsym(oracle,"elpis_streaming_regex_parse_bytes_v1"));
        frozen_json=reinterpret_cast<decltype(frozen_json)>(dlsym(oracle,"elpis_streaming_regex_result_json_v1"));
        frozen_destroy=reinterpret_cast<decltype(frozen_destroy)>(dlsym(oracle,"elpis_streaming_regex_result_destroy_v1"));
        require(frozen_parse && frozen_json && frozen_destroy,"oracle symbols");
    }
    lifecycle(); invalid_utf8();
    std::cout<<"PASS_V2_LIFECYCLE_UTF8"<<std::endl;
    std::mt19937 random(0x51a7);
    auto fs=fixtures();
    for(const auto& text:fs) {
        for(size_t chunk:{1u,2u,7u,13u,4096u}) parity(text,std::vector<size_t>(text.size()/chunk+1,chunk));
        for(size_t split=0;split<=text.size();++split) parity(text,{split});
        std::vector<size_t> parts; for(size_t n=0;n<text.size();) { size_t k=1+random()%17; parts.push_back(k); n+=k; } parity(text,parts);
    }
    for(size_t i=0;i<120;++i) {
        std::string text;
        for(size_t k=0;k<4;++k) text+=fs[random()%fs.size()]+(random()%2?"; ":" ");
        parity(text,{1,2,7,11,19,23});
    }
    std::cout<<"PASS_V2_PARITY runs="<<parity_runs<<std::endl;
    long_stream();
    if(oracle) dlclose(oracle);
    std::cout<<"PASS_V2_STREAM parity_runs="<<parity_runs<<" fixtures="<<fs.size()<<"\n";
}
