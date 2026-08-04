#include "r3_test_support.h"
#include <atomic>
#include <cstdio>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

static int checks=0,fails=0;
#define CHECK(x) do{++checks;if(!(x)){++fails;std::printf("FAIL %s:%d %s\n",__FILE__,__LINE__,#x);}}while(0)
int main(int argc,char**argv){
    r3t::Env e;CHECK(e.build(argc>1?argv[1]:"/tmp/r3-conc")==0);elpis_context_graph*g=r3t::graph_for(e,true);CHECK(g!=nullptr);
    elpis_hybrid_policy p{};elpis_hybrid_policy_default(&p);p.lexical_limit=4;p.dense_limit=4;p.primary_limit=1;p.graph_seed_limit=1;p.graph_neighbors_per_seed=1;p.total_limit=2;
    elpis_hybrid_retriever*r=nullptr;CHECK(elpis_hybrid_retriever_create(e.corpus,e.index,g,&p,&r)==0);
    std::vector<float>qv=e.embed(e.text_by_label["beta"]);elpis_hybrid_query q{};q.text=e.text_by_label["alpha"].c_str();q.vector=qv.data();q.dimensions=ELPIS_EMBEDDING_DIM;
    elpis_retrieval_bundle*base=nullptr;CHECK(elpis_hybrid_retrieve(r,&q,&base)==0);char expected[65];CHECK(elpis_retrieval_bundle_identity(base,nullptr,nullptr,nullptr,nullptr,nullptr,expected,nullptr)==0);elpis_retrieval_bundle_destroy(base);
    std::atomic<int>bad{0};std::vector<std::thread>ts;for(int t=0;t<4;++t)ts.emplace_back([&]{for(int i=0;i<20;++i){elpis_retrieval_bundle*b=nullptr;if(elpis_hybrid_retrieve(r,&q,&b)!=0){bad++;continue;}char d[65];if(elpis_retrieval_bundle_identity(b,nullptr,nullptr,nullptr,nullptr,nullptr,d,nullptr)!=0||std::strcmp(d,expected)!=0)bad++;elpis_retrieval_bundle_destroy(b);}});for(auto&t:ts)t.join();CHECK(bad.load()==0);
    elpis_hybrid_retriever_destroy(r);elpis_context_graph_destroy(g);std::printf("hybrid_concurrency: %d checks, %d failures\n",checks,fails);return fails?1:0;
}
