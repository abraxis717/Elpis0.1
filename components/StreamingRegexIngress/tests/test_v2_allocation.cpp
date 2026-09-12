#include "streaming_regex_ingress_v2.h"
#include <cstdlib>
#include <iostream>
#include <new>
#include <cstring>
// Process-local deterministic failure injection; production has no test hook.
static long remaining=-1;
void* operator new(std::size_t n) {
    if(remaining==0) throw std::bad_alloc();
    if(remaining>0) --remaining;
    if(void* p=std::malloc(n?n:1)) return p;
    throw std::bad_alloc();
}
void* operator new[](std::size_t n) { return ::operator new(n); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p,std::size_t) noexcept { std::free(p); }
void operator delete[](void* p,std::size_t) noexcept { std::free(p); }
static void check(bool ok) { if(!ok) { std::cerr<<"allocation atomicity failure\n"; std::exit(1); } }
int main() {
    unsigned failed_create=0,failed_feed=0,failed_finish=0;
    for(long n:{0L,1L,2L,4L,8L,16L,32L,64L,128L,256L,512L,1024L}) {
        elpis_streaming_regex_stream_v2* s=nullptr;
        remaining=n;
        int rc=elpis_streaming_regex_stream_create_v2(nullptr,&s);
        remaining=-1;
        check((rc==-3 && !s) || (rc==0 && s));
        failed_create+=rc==-3;
        elpis_streaming_regex_stream_destroy_v2(s);
    }
    const char* text="keep some_value between lower and upper; exactly 7.5; maximum end";
    for(long n:{0L,1L,2L,4L,8L,16L,32L,64L,128L,256L,512L}) {
        elpis_streaming_regex_stream_v2* s=nullptr;
        check(elpis_streaming_regex_stream_create_v2(nullptr,&s)==0);
        remaining=n;
        int rc=elpis_streaming_regex_stream_feed_v2(s,reinterpret_cast<const uint8_t*>(text),std::strlen(text));
        remaining=-1;
        check(rc==-3 || rc==0); failed_feed+=rc==-3;
        elpis_streaming_regex_result_v1* r=nullptr;
        if(rc) check(elpis_streaming_regex_stream_finalize_v2(s,&r)==-3 && !r);
        elpis_streaming_regex_stream_destroy_v2(s);
    }
    for(long n:{0L,1L,2L,4L,8L,16L,32L,64L,128L,256L,512L,1024L}) {
        elpis_streaming_regex_stream_v2* s=nullptr;
        check(elpis_streaming_regex_stream_create_v2(nullptr,&s)==0);
        check(elpis_streaming_regex_stream_feed_v2(s,reinterpret_cast<const uint8_t*>(text),std::strlen(text))==0);
        elpis_streaming_regex_result_v1* r=nullptr;
        remaining=n;
        int rc=elpis_streaming_regex_stream_finalize_v2(s,&r);
        remaining=-1;
        check((rc==-3 && !r) || (rc==0 && r)); failed_finish+=rc==-3;
        if(rc) check(elpis_streaming_regex_stream_finalize_v2(s,&r)==-3 && !r);
        elpis_streaming_regex_result_destroy_v1(r);
        elpis_streaming_regex_stream_destroy_v2(s);
    }
    check(failed_create && failed_feed && failed_finish);
    std::cout<<"PASS_V2_ALLOCATION create="<<failed_create<<" feed="<<failed_feed<<" finalize="<<failed_finish<<"\n";
}
