#include "r3_test_support.h"
#include <cstdio>
#include <cstring>
#include <sys/stat.h>

static int checks=0,fails=0;
#define CHECK(x) do{++checks;if(!(x)){++fails;std::printf("FAIL %s:%d %s\n",__FILE__,__LINE__,#x);}}while(0)
int main(int argc,char**argv){
    std::string root=argc>1?argv[1]:"/tmp/r3-bundle"; r3t::Env e; CHECK(e.build(root)==0);
    elpis_context_graph*g=r3t::graph_for(e);CHECK(g!=nullptr);
    elpis_hybrid_policy p{};elpis_hybrid_policy_default(&p);p.primary_limit=1;p.graph_seed_limit=1;p.graph_neighbors_per_seed=1;p.total_limit=2;
    elpis_hybrid_retriever*r=nullptr;CHECK(elpis_hybrid_retriever_create(e.corpus,e.index,g,&p,&r)==0);
    std::vector<float>v;auto q=r3t::query(e,"alpha","beta",v);elpis_retrieval_bundle*b=nullptr;CHECK(elpis_hybrid_retrieve(r,&q,&b)==0);CHECK(elpis_retrieval_bundle_item_count(b)==2);
    elpis_retrieval_item_view a{},c{};CHECK(elpis_retrieval_bundle_item(b,0,&a)==0);CHECK(elpis_retrieval_bundle_item(b,1,&c)==0);CHECK(a.item_kind==ELPIS_RITEM_PRIMARY);CHECK(c.item_kind==ELPIS_RITEM_CONTEXT);CHECK(c.graph_hop==1);CHECK(std::strcmp(c.graph_parent_digest,a.chunk_digest)==0);CHECK(c.text&&c.text_bytes>0);
    char *j=nullptr,d[65],pkg[65];CHECK(elpis_retrieval_bundle_json(b,&j,d)==0);CHECK(std::strstr(j,"elpis.retrieval_bundle.v1")!=nullptr);CHECK(std::strstr(j,"\"text_hex\"")!=nullptr);CHECK(elpis_retrieval_bundle_identity(b,nullptr,nullptr,nullptr,nullptr,nullptr,nullptr,pkg)==0);CHECK(std::strcmp(d,pkg)!=0);
    std::string path=root+"/bundle.json";char wd[65];CHECK(elpis_retrieval_bundle_write(b,path.c_str(),wd)==0);CHECK(std::strcmp(wd,d)==0);CHECK(elpis_retrieval_bundle_write(b,path.c_str(),wd)!=0);elpis_free(j);
    elpis_retrieval_bundle_destroy(b);elpis_hybrid_retriever_destroy(r);elpis_context_graph_destroy(g);
    std::printf("retrieval_bundle: %d checks, %d failures\n",checks,fails);return fails?1:0;
}
