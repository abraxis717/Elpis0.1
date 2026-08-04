#include "r3_test_support.h"
#include "elpis/chunking.h"
#include <cstdio>
#include <cstring>

static int checks=0,fails=0;
#define CHECK(x) do{++checks;if(!(x)){++fails;std::printf("FAIL %s:%d %s\n",__FILE__,__LINE__,#x);}}while(0)
int main(int argc,char**argv){
    r3t::Env e; CHECK(e.build(argc>1?argv[1]:"/tmp/r3-fusion")==0);
    elpis_hybrid_policy p{}; CHECK(elpis_hybrid_policy_default(&p)==0); p.primary_limit=3;p.total_limit=3;p.graph_seed_limit=0;p.graph_neighbors_per_seed=0;
    elpis_hybrid_retriever *r=nullptr; CHECK(elpis_hybrid_retriever_create(e.corpus,e.index,nullptr,&p,&r)==0);
    std::vector<float> v; auto q=r3t::query(e,"alpha","beta",v);
    elpis_retrieval_bundle *b1=nullptr,*b2=nullptr; int rc1=elpis_hybrid_retrieve(r,&q,&b1); if(rc1) std::printf("rc1=%d err=%s\n",rc1,elpis_hybrid_retriever_error(r)); CHECK(rc1==0); int rc2=elpis_hybrid_retrieve(r,&q,&b2); if(rc2) std::printf("rc2=%d err=%s\n",rc2,elpis_hybrid_retriever_error(r)); CHECK(rc2==0);
    CHECK(elpis_retrieval_bundle_item_count(b1)==3);
    char d1[65],d2[65]; CHECK(elpis_retrieval_bundle_identity(b1,nullptr,nullptr,nullptr,nullptr,nullptr,d1,nullptr)==0); CHECK(elpis_retrieval_bundle_identity(b2,nullptr,nullptr,nullptr,nullptr,nullptr,d2,nullptr)==0); CHECK(std::strcmp(d1,d2)==0);
    elpis_retrieval_item_view i0{},i1{}; CHECK(elpis_retrieval_bundle_item(b1,0,&i0)==0); CHECK(elpis_retrieval_bundle_item(b1,1,&i1)==0);
    CHECK(i0.item_kind==ELPIS_RITEM_PRIMARY && i1.item_kind==ELPIS_RITEM_PRIMARY);
    CHECK((i0.source_mask|i1.source_mask)&ELPIS_RSRC_LEXICAL); CHECK((i0.source_mask|i1.source_mask)&ELPIS_RSRC_DENSE);
    if(i0.fusion_score_key==i1.fusion_score_key) CHECK(std::strcmp(i0.chunk_digest,i1.chunk_digest)<0);
    elpis_retrieval_bundle_destroy(b1);elpis_retrieval_bundle_destroy(b2);
    q.namespace_filter="bad\nns"; b1=nullptr; CHECK(elpis_hybrid_retrieve(r,&q,&b1)==ELPIS_HYBRID_E_INVAL);
    q.namespace_filter=nullptr;
    elpis_ingest_meta m{"elpis.docs","reference",ELPIS_MT_TEXT,"drift"}; elpis_ingest_result ir{}; const char*z="new drift document";
    CHECK(elpis_corpus_ingest_bytes(e.corpus,z,std::strlen(z),&m,&ir)==0); CHECK(elpis_hybrid_retrieve(r,&q,&b1)==ELPIS_HYBRID_E_DRIFT);
    elpis_hybrid_retriever_destroy(r);
    std::printf("hybrid_fusion: %d checks, %d failures\n",checks,fails);return fails?1:0;
}
