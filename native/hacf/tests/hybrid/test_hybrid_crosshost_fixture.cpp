/* Gate R3 cross-host fixture: the committed synthetic corpus in
 * r3_test_support.h is run through corpus -> exact vector index -> deterministic
 * RRF -> one-hop graph expansion -> frozen RetrievalBundle. */
#include "r3_test_support.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <map>
#include <sstream>
#include <string>

#ifndef HACF_R3_FIXTURE_DIR
#define HACF_R3_FIXTURE_DIR "tests/hybrid/fixture"
#endif

static int checks=0,fails=0;
#define CHECK(x) do{++checks;if(!(x)){++fails;std::printf("FAIL %s:%d %s\n",__FILE__,__LINE__,#x);}}while(0)
static std::map<std::string,std::string> parse(const std::string&s){std::map<std::string,std::string>m;std::istringstream in(s);std::string l;while(std::getline(in,l)){if(l.empty()||l[0]=='#')continue;auto p=l.find('=');if(p!=std::string::npos)m[l.substr(0,p)]=l.substr(p+1);}return m;}
static std::string slurp(const std::string&p){std::ifstream f(p);return std::string((std::istreambuf_iterator<char>(f)),{});}
int main(int argc,char**argv){
    std::string root=argc>1?argv[1]:"/tmp/r3-xhost";r3t::Env e;CHECK(e.build(root)==0);
    elpis_context_graph*g=r3t::graph_for(e,true);CHECK(g!=nullptr);
    elpis_hybrid_policy p{};elpis_hybrid_policy_default(&p);p.lexical_limit=4;p.dense_limit=4;p.primary_limit=1;p.graph_seed_limit=1;p.graph_neighbors_per_seed=1;p.total_limit=2;
    char policy[65],graph[65];CHECK(elpis_hybrid_policy_digest(&p,policy)==0);CHECK(elpis_context_graph_digest(g,graph)==0);
    char*ij=nullptr,index[65];CHECK(elpis_vector_index_manifest_json(e.index,&ij,index)==0);elpis_free(ij);
    elpis_hybrid_retriever*r=nullptr;CHECK(elpis_hybrid_retriever_create(e.corpus,e.index,g,&p,&r)==0);
    std::vector<float>v;auto q=r3t::query(e,"alpha","beta",v);elpis_retrieval_bundle*b=nullptr;CHECK(elpis_hybrid_retrieve(r,&q,&b)==0);
    char query[65],corpus[65],vid[65],gid[65],pid[65],bundle[65],package[65];CHECK(elpis_retrieval_bundle_identity(b,query,corpus,vid,gid,pid,bundle,package)==0);
    std::string actual="# HACF R3 cross-host fixture expectations\n# Regenerate only for a deliberate R3 ABI or policy change.\n";
    actual+="policy_digest="+std::string(policy)+"\n";actual+="graph_digest="+std::string(graph)+"\n";actual+="corpus_manifest_digest="+std::string(corpus)+"\n";actual+="index_manifest_digest="+std::string(index)+"\n";actual+="query_digest="+std::string(query)+"\n";actual+="bundle_digest="+std::string(bundle)+"\n";actual+="package_digest="+std::string(package)+"\n";actual+="item_count="+std::to_string(elpis_retrieval_bundle_item_count(b))+"\n";
    for(uint32_t i=0;i<elpis_retrieval_bundle_item_count(b);++i){elpis_retrieval_item_view x{};elpis_retrieval_bundle_item(b,i,&x);actual+="item_"+std::to_string(i)+"="+x.chunk_digest+":"+std::to_string(x.source_mask)+":"+std::to_string(x.fusion_score_key)+":"+std::to_string(x.graph_hop)+"\n";}
    std::string path=std::string(HACF_R3_FIXTURE_DIR)+"/expected.txt";
    if(std::getenv("ELPIS_R3_FIXTURE_REGENERATE")){std::ofstream f(path,std::ios::trunc);f<<actual;std::printf("regenerated %s\n",path.c_str());}
    auto a=parse(actual),eexp=parse(slurp(path));CHECK(!eexp.empty());CHECK(a==eexp);
    std::printf("R3 cross-host fixture\n%s",actual.c_str());std::printf("%d checks, %d failures\n",checks,fails);
    elpis_retrieval_bundle_destroy(b);elpis_hybrid_retriever_destroy(r);elpis_context_graph_destroy(g);return fails?1:0;
}
