#include "streaming_regex_ingress_v2.h"
#include <cstddef>
#include <cstdlib>
#include <iostream>
#include <new>
#include <string>
// Track all C++ allocations, including any hypothetical hidden source string.
// PCRE2 malloc state is fixed per grammar/handle; this measures stream growth.
struct alignas(std::max_align_t) Header { size_t size; };
static size_t live=0, peak=0;
void* operator new(size_t n) {
    if(n>SIZE_MAX-sizeof(Header)) throw std::bad_alloc();
    auto* h=static_cast<Header*>(std::malloc(sizeof(Header)+(n?n:1)));
    if(!h) throw std::bad_alloc();
    h->size=n; live+=n; if(live>peak) peak=live; return h+1;
}
void* operator new[](size_t n) { return ::operator new(n); }
void operator delete(void* p) noexcept {
    if(p) { auto* h=static_cast<Header*>(p)-1; live-=h->size; std::free(h); }
}
void operator delete[](void* p) noexcept { ::operator delete(p); }
void operator delete(void* p,size_t) noexcept { ::operator delete(p); }
void operator delete[](void* p,size_t) noexcept { ::operator delete(p); }
static void req(bool b,const char* why) { if(!b) { std::cerr<<why<<"\n"; std::exit(1); } }
int main() {
    const std::string block(65536,'z'), spaces(65536,' ');
    for(bool whitespace:{false,true}) {
        elpis_streaming_regex_stream_v2* s=nullptr;
        req(elpis_streaming_regex_stream_create_v2(nullptr,&s)==0,"create");
        if(whitespace) req(elpis_streaming_regex_stream_feed_v2(s,reinterpret_cast<const uint8_t*>("at"),2)==0,"prefix");
        size_t before=0, later=0, early_peak=0;
        const auto& input=whitespace?spaces:block;
        peak=live;
        const size_t iterations=whitespace?48:800;
        for(size_t i=0;i<iterations;++i) {
            req(elpis_streaming_regex_stream_feed_v2(s,reinterpret_cast<const uint8_t*>(input.data()),input.size())==0,"feed");
            if(i==15) { before=live; early_peak=peak; }
        }
        later=live;
        req(before==later && peak==early_peak,"working allocation growth with unrelated source length");
        req(later<1024*1024 && peak<2*1024*1024,"absolute measured allocation bound");
        if(whitespace) req(elpis_streaming_regex_stream_feed_v2(s,reinterpret_cast<const uint8_t*>("least 1"),7)==0,"suffix");
        elpis_streaming_regex_result_v1* r=nullptr;
        req(elpis_streaming_regex_stream_finalize_v2(s,&r)==0,"finalize");
        req(elpis_streaming_regex_result_evidence_count_v1(r)==static_cast<uint32_t>(whitespace),"evidence");
        elpis_streaming_regex_result_destroy_v1(r); elpis_streaming_regex_stream_destroy_v2(s);
        std::cout<<(whitespace?"whitespace":"no_match")<<" input_bytes="<<iterations*input.size()<<" live_after_1MiB="<<before<<" live_at_end="<<later<<" peak="<<early_peak<<"\n";
    }
    std::cout<<"PASS_V2_ALLOCATION_BOUND\n";
}
