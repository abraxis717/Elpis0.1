#include "elpis_semantic/embedding_view.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL %d: %s\n",__LINE__,#x); exit(1); } } while(0)
int main(void) {
    semantic_snapshot_manifest *m=semantic_snapshot_create();
    semantic_snapshot_view *base=semantic_view_create(m); CHECK(base);
    elpis_semantic_node_v1 nodes[5]={{0}};
    for(unsigned i=0;i<5;++i) nodes[i].node_identity.bytes[0]=(uint8_t)(5-i);
    semantic_view_set_records(base,nodes,5,NULL,0,NULL,0,NULL,0);
    elpis_semantic_embedding_collection_v1 cols[2]={{0}};
    embedding_composed_view *v=embedding_composed_view_create(base,NULL,NULL,cols,2); CHECK(v);
    elpis_semantic_embedding_ref_v1 refs[7]={{0}};
    const unsigned ids[]={5,99,3,5,1,3,5};
    for(unsigned i=0;i<7;++i) {
        refs[i].semantic_node_digest.bytes[0]=(uint8_t)ids[i];
        refs[i].embedding_vector_digest.bytes[0]=1;
        refs[i].embedding_profile_digest.bytes[0]=1;
        refs[i].provenance_digest.bytes[0]=1; refs[i].authority=2;
    }
    embedding_composed_view_set_refs(v,refs,7);
    const elpis_semantic_node_v1 *out[8], *expected[3];
    for(unsigned i=0;i<3;++i) { hacf_digest d={{(uint8_t)(1+2*i)}}; expected[i]=semantic_view_lookup_node(base,&d); CHECK(expected[i]); }
    const uint32_t offsets[]={0,1,3,4,UINT32_MAX}, limits[]={0,1,2,3,UINT32_MAX}, capacities[]={0,1,2,3,8};
    for(unsigned a=0;a<5;++a) for(unsigned b=0;b<5;++b) for(unsigned c=0;c<5;++c) {
        uint32_t want=offsets[a]<3 ? 3-offsets[a] : 0;
        if(want>limits[b]) want=limits[b]; if(want>capacities[c]) want=capacities[c];
        for(unsigned repeat=0;repeat<2;++repeat) {
            for(unsigned i=0;i<8;++i) out[i]=expected[0];
            CHECK(embedding_composed_view_enumerate_embedded_nodes(v,offsets[a],limits[b],out,capacities[c])==want);
            for(unsigned i=0;i<want;++i) CHECK(out[i]==expected[offsets[a]+i]);
            for(unsigned i=want;i<8;++i) CHECK(out[i]==expected[0]);
        }
    }
    CHECK(embedding_composed_view_enumerate_embedded_nodes(v,0,5,NULL,5)==0);
    const elpis_semantic_embedding_ref_v1 *rout[4]={&refs[1],&refs[1],&refs[1],&refs[1]};
    hacf_digest node={{5}}, filter={{1}};
#define REFS(call) do { CHECK((call)==2); CHECK(rout[0]==&refs[0] && rout[1]==&refs[3] && rout[2]==&refs[1]); } while(0)
    REFS(embedding_composed_view_node_refs(v,&node,rout,2));
    REFS(embedding_composed_view_node_refs_by_profile(v,&node,&filter,rout,2));
    REFS(embedding_composed_view_node_refs_by_provenance(v,&node,&filter,rout,2));
    REFS(embedding_composed_view_node_refs_by_authority(v,&node,2,rout,2));
    CHECK(embedding_composed_view_node_refs(v,&node,NULL,4)==0);
    CHECK(embedding_composed_view_node_refs_by_profile(v,&node,&filter,NULL,4)==0);
    CHECK(embedding_composed_view_node_refs_by_provenance(v,&node,&filter,NULL,4)==0);
    CHECK(embedding_composed_view_node_refs_by_authority(v,&node,2,NULL,4)==0);
    CHECK(embedding_composed_view_node_refs(v,&node,rout,0)==0 && rout[0]==&refs[0]);
    hacf_digest vectors[5]; memset(vectors,0xa5,sizeof(vectors));
    CHECK(embedding_composed_view_nodes_for_vector(v,&filter,NULL,4)==0);
    CHECK(embedding_composed_view_nodes_for_vector(v,&filter,vectors,0)==0 && vectors[0].bytes[0]==0xa5);
    CHECK(embedding_composed_view_nodes_for_vector(v,&filter,vectors,5)==4);
    CHECK(vectors[0].bytes[0]==5 && vectors[1].bytes[0]==99 && vectors[2].bytes[0]==3 && vectors[3].bytes[0]==1);
    CHECK(vectors[4].bytes[0]==0xa5);
    CHECK(embedding_composed_view_nodes_for_vector(v,&filter,vectors,2)==2);
    const elpis_semantic_embedding_collection_v1 *cout[2]={&cols[0],&cols[0]};
    CHECK(embedding_composed_view_collections(v,0,2,NULL,2)==0);
    CHECK(embedding_composed_view_collections(v,0,0,cout,2)==0 && cout[0]==&cols[0]);
    CHECK(embedding_composed_view_collections(v,0,2,cout,0)==0 && cout[0]==&cols[0]);
    CHECK(embedding_composed_view_collections(v,1,2,cout,1)==1 && cout[0]==&cols[1] && cout[1]==&cols[0]);
    CHECK(embedding_composed_view_create(base,NULL,NULL,NULL,1)==NULL);
    embedding_composed_view_set_refs(NULL,refs,7);
    embedding_composed_view_set_refs(v,NULL,1);
    CHECK(v->refs==refs && v->ref_count==7);
    embedding_composed_view_set_refs(v,NULL,0);
    CHECK(embedding_composed_view_enumerate_embedded_nodes(v,0,5,out,5)==0);
    embedding_composed_view_set_refs(v,&refs[1],1); /* only absent base node */
    CHECK(embedding_composed_view_enumerate_embedded_nodes(v,0,5,out,5)==0);
    embedding_composed_view_set_refs(v,refs,7);
    semantic_view_set_records(base,NULL,0,NULL,0,NULL,0,NULL,0);
    CHECK(embedding_composed_view_enumerate_embedded_nodes(v,0,5,out,5)==0);
    embedding_composed_view_destroy(v); semantic_view_destroy(base); semantic_snapshot_destroy(m);
    puts("PASS embedding view contract"); return 0;
}
