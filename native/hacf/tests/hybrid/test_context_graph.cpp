#include "elpis/context_graph.h"
#include "elpis/corpus.h"
#include "r2_test_support.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <vector>

static int checks=0, fails=0;
#define CHECK(x) do { ++checks; if(!(x)){++fails; std::printf("FAIL %s:%d %s\n",__FILE__,__LINE__,#x);} } while(0)

static elpis_context_edge_input edge(const char *a, const char *b, uint32_t t, uint32_t auth) {
    elpis_context_edge_input e{};
    std::string sa=r2t::hex_of(a), sb=r2t::hex_of(b), sp=r2t::hex_of(std::string(a)+"/"+b);
    std::snprintf(e.subject_chunk_digest,65,"%s",sa.c_str());
    std::snprintf(e.object_chunk_digest,65,"%s",sb.c_str());
    std::snprintf(e.provenance_digest,65,"%s",sp.c_str()); e.edge_type=t; e.authority=auth; return e;
}
int main(){
    auto a=edge("a","b",2,1), b=edge("a","c",1,2), c=edge("a","d",1,3);
    std::vector<elpis_context_edge_input> x={a,b,c,a}, y={c,a,b};
    elpis_context_graph *g1=nullptr,*g2=nullptr;
    CHECK(elpis_context_graph_create(x.data(),x.size(),&g1)==0);
    CHECK(elpis_context_graph_create(y.data(),y.size(),&g2)==0);
    CHECK(elpis_context_graph_edge_count(g1)==3);
    char d1[65],d2[65]; CHECK(elpis_context_graph_digest(g1,d1)==0); CHECK(elpis_context_graph_digest(g2,d2)==0);
    CHECK(std::strcmp(d1,d2)==0);
    elpis_context_neighbor n[4]{}; uint32_t got=0;
    CHECK(elpis_context_graph_neighbors(g1,a.subject_chunk_digest,0,0,4,n,&got)==0); CHECK(got==3);
    CHECK(n[0].edge_type==1 && n[1].edge_type==1 && n[2].edge_type==2);
    CHECK(std::strcmp(n[0].chunk_digest,n[1].chunk_digest)<0);
    CHECK(elpis_context_graph_neighbors(g1,a.subject_chunk_digest,3,0,2,n,&got)==0); CHECK(got==1); CHECK(n[0].authority==3);
    char *j1=nullptr,*j2=nullptr,m1[65],m2[65];
    CHECK(elpis_context_graph_manifest_json(g1,&j1,m1)==0); CHECK(elpis_context_graph_manifest_json(g2,&j2,m2)==0);
    CHECK(std::strcmp(j1,j2)==0 && std::strcmp(m1,m2)==0); elpis_free(j1); elpis_free(j2);
    auto self=edge("z","z",1,1); elpis_context_graph *bad=nullptr; CHECK(elpis_context_graph_create(&self,1,&bad)!=0);
    a.subject_chunk_digest[0]='A'; CHECK(elpis_context_graph_create(&a,1,&bad)!=0);
    elpis_context_graph_destroy(g1); elpis_context_graph_destroy(g2);
    std::printf("context_graph: %d checks, %d failures\n",checks,fails); return fails?1:0;
}
