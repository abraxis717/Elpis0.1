#include "r3_test_support.h"
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <vector>

int main(int argc,char**argv){
    std::string root=argc>1?argv[1]:"/tmp/r3-bench";r3t::Env e;if(e.build(root)!=0)return 2;
    elpis_context_graph*g=r3t::graph_for(e,true);if(!g)return 2;
    elpis_hybrid_policy p{};elpis_hybrid_policy_default(&p);p.lexical_limit=4;p.dense_limit=4;p.primary_limit=1;p.graph_seed_limit=1;p.graph_neighbors_per_seed=1;p.total_limit=2;
    elpis_hybrid_retriever*r=nullptr;if(elpis_hybrid_retriever_create(e.corpus,e.index,g,&p,&r)!=0)return 2;
    std::vector<float>v;auto q=r3t::query(e,"alpha","beta",v);std::vector<double>ms;char final_digest[65]{};
    for(int i=0;i<200;++i){auto t0=std::chrono::steady_clock::now();elpis_retrieval_bundle*b=nullptr;if(elpis_hybrid_retrieve(r,&q,&b)!=0)return 2;auto t1=std::chrono::steady_clock::now();ms.push_back(std::chrono::duration<double,std::milli>(t1-t0).count());elpis_retrieval_bundle_identity(b,nullptr,nullptr,nullptr,nullptr,nullptr,final_digest,nullptr);elpis_retrieval_bundle_destroy(b);}
    std::sort(ms.begin(),ms.end());double p50=ms[ms.size()/2],p95=ms[(ms.size()*95)/100];
    std::printf("{\"bundle_digest\":\"%s\",\"iterations\":200,\"p50_ms\":%.6f,\"p95_ms\":%.6f,\"schema\":\"elpis.hybrid_benchmark.v1\"}\n",final_digest,p50,p95);
    elpis_hybrid_retriever_destroy(r);elpis_context_graph_destroy(g);return 0;
}
