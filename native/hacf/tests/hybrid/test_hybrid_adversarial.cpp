#include "r3_test_support.h"
#include <cmath>
#include <cstdio>
#include <cstring>

static int checks=0,fails=0;
#define CHECK(x) do{++checks;if(!(x)){++fails;std::printf("FAIL %s:%d %s\n",__FILE__,__LINE__,#x);}}while(0)
int main(int argc,char**argv){
    r3t::Env e;CHECK(e.build(argc>1?argv[1]:"/tmp/r3-adv")==0);
    elpis_hybrid_policy p{};elpis_hybrid_policy_default(&p);char pd1[65],pd2[65];CHECK(elpis_hybrid_policy_digest(&p,pd1)==0);CHECK(elpis_hybrid_policy_digest(&p,pd2)==0);CHECK(std::strcmp(pd1,pd2)==0);
    auto bad=p;bad.reserved[0]=1;CHECK(elpis_hybrid_policy_validate(&bad)!=0);bad=p;bad.total_limit=257;CHECK(elpis_hybrid_policy_validate(&bad)!=0);bad=p;bad.primary_limit=bad.total_limit+1;CHECK(elpis_hybrid_policy_validate(&bad)!=0);
    elpis_context_graph*g=r3t::graph_for(e,true);CHECK(g!=nullptr);p.primary_limit=1;p.graph_seed_limit=1;p.graph_neighbors_per_seed=4;p.total_limit=4;
    elpis_hybrid_retriever*r=nullptr;CHECK(elpis_hybrid_retriever_create(e.corpus,e.index,g,&p,&r)==0);
    std::vector<float>v;auto q=r3t::query(e,"alpha","beta",v);elpis_retrieval_bundle*b=nullptr;CHECK(elpis_hybrid_retrieve(r,&q,&b)==0);
    bool saw_delta=false;for(uint32_t i=0;i<elpis_retrieval_bundle_item_count(b);++i){elpis_retrieval_item_view x{};elpis_retrieval_bundle_item(b,i,&x);if(std::strcmp(x.chunk_digest,e.ref_by_label["delta"].chunk_digest)==0)saw_delta=true;CHECK(x.graph_hop<=1);}CHECK(!saw_delta);elpis_retrieval_bundle_destroy(b);
    q.authority_filter="bogus";CHECK(elpis_hybrid_retrieve(r,&q,&b)==ELPIS_HYBRID_E_INVAL);q.authority_filter=nullptr;v[0]=NAN;CHECK(elpis_hybrid_retrieve(r,&q,&b)==ELPIS_HYBRID_E_INVAL);v=e.embed(e.text_by_label["beta"]);q.vector=v.data();
    elpis_chunk_ref ref{};std::string upper=e.ref_by_label["alpha"].chunk_digest;upper[0]='A';CHECK(elpis_corpus_chunk_lookup(e.corpus,upper.c_str(),&ref)!=0);
    elpis_hybrid_retriever_destroy(r);elpis_context_graph_destroy(g);
    /* Graph integrity: canonical edge to an absent chunk is a hard failure. */
    elpis_context_edge_input edge{};std::snprintf(edge.subject_chunk_digest,65,"%s",e.ref_by_label["alpha"].chunk_digest);std::string missing=r2t::hex_of("missing");std::snprintf(edge.object_chunk_digest,65,"%s",missing.c_str());std::string prov=r2t::hex_of("prov");std::snprintf(edge.provenance_digest,65,"%s",prov.c_str());edge.edge_type=1;edge.authority=2;elpis_context_graph*gm=nullptr;CHECK(elpis_context_graph_create(&edge,1,&gm)==0);CHECK(elpis_hybrid_retriever_create(e.corpus,e.index,gm,&p,&r)==0);q.text=e.text_by_label["alpha"].c_str();v=e.embed(e.text_by_label["alpha"]);q.vector=v.data();CHECK(elpis_hybrid_retrieve(r,&q,&b)==ELPIS_HYBRID_E_INTEGRITY);elpis_hybrid_retriever_destroy(r);elpis_context_graph_destroy(gm);
    std::printf("hybrid_adversarial: %d checks, %d failures\n",checks,fails);return fails?1:0;
}
