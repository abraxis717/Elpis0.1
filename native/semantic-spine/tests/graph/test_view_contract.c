#include "elpis_semantic/snapshot_view.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"FAIL %d: %s\n",__LINE__,#x); exit(1); } } while (0)

#ifdef VIEW_WRAP_ALLOC
static int fail_after = -1;
void *__real_malloc(size_t size);
void *__wrap_malloc(size_t size) {
    if (fail_after == 0) return NULL;
    if (fail_after > 0) --fail_after;
    return __real_malloc(size);
}
#endif

/* Run the complete pagination boundary matrix through each typed public API. */
#define PAGES(type, call) do { \
    const type *out[12], *expected[12]; \
    uint32_t offset=0, limit=12, capacity=12; \
    uint32_t total=(call); CHECK(total == 4); \
    for (unsigned k=0;k<total;++k) expected[k]=out[k]; \
    const uint32_t offsets[]={0,1,4,5,UINT32_MAX}; \
    const uint32_t limits[]={0,1,3,4,UINT32_MAX}; \
    const uint32_t capacities[]={0,1,3,4,12}; \
    for(unsigned a=0;a<5;++a) for(unsigned b=0;b<5;++b) for(unsigned c=0;c<5;++c) { \
        offset=offsets[a]; limit=limits[b]; capacity=capacities[c]; \
        uint32_t want=offset<total ? total-offset : 0; \
        if(want>limit) want=limit; if(want>capacity) want=capacity; \
        for(unsigned repeat=0;repeat<2;++repeat) { \
            for(unsigned k=0;k<12;++k) out[k]=expected[0]; \
            CHECK((call)==want); \
            for(unsigned k=0;k<want;++k) CHECK(out[k]==expected[offset+k]); \
            for(unsigned k=want;k<12;++k) CHECK(out[k]==expected[0]); \
        } \
    } \
} while(0)

int main(void) {
    semantic_snapshot_manifest *m=semantic_snapshot_create();
    semantic_snapshot_view *v=semantic_view_create(m); CHECK(v);
    elpis_semantic_node_v1 nodes[7]={{0}};
    elpis_semantic_hyperedge_v1 edges[7]={{0}};
    elpis_semantic_incidence_v1 inc[7]={{0}};
    elpis_semantic_assertion_v1 assertions[17]={{0}};
    hacf_digest node={{1}}, edge={{1}};
    for(unsigned i=0;i<7;++i) {
        nodes[i].node_identity.bytes[0]=(uint8_t)(i+1); nodes[i].node_type=1+i%2;
        edges[i].hyperedge_identity.bytes[0]=(uint8_t)(i+1); edges[i].hyperedge_type=1+i%2;
        edges[i].participant_count=i%2 ? 0 : 1;
        edges[i].participants[0].node_identity=node;
        inc[i].incidence_role=1+i%2; inc[i].ordinal=i;
        for(unsigned j=0;j<2;++j) {
            elpis_semantic_assertion_v1 *a=&assertions[j*7+i];
            a->asserted_object_digest=node; a->asserted_object_kind=j ? SEMANTIC_OBJECT_KIND_HYPEREDGE : SEMANTIC_OBJECT_KIND_NODE;
            a->provenance_digest.bytes[0]=(uint8_t)(i+1); a->authority=i%2 ? 1 : 3;
        }
    }
    edges[0].participant_count=4;
    for(unsigned i=0;i<4;++i) { edges[0].participants[i].node_identity=node; edges[0].participants[i].ordinal=i; }
    for(unsigned i=0;i<3;++i) { assertions[14+i].asserted_object_kind=SEMANTIC_OBJECT_KIND_NODE;
        assertions[14+i].asserted_object_digest.bytes[0]=(uint8_t)(3+2*i); assertions[14+i].authority=3; }
    semantic_view_set_records(v,nodes,7,assertions,17,edges,7,inc,7);
    PAGES(elpis_semantic_assertion_v1,semantic_view_node_assertions(v,&node,2,offset,limit,out,capacity));
    PAGES(elpis_semantic_assertion_v1,semantic_view_hyperedge_assertions(v,&edge,2,offset,limit,out,capacity));
    PAGES(elpis_semantic_participant_descriptor,semantic_view_hyperedge_participants(v,&edge,offset,limit,out,capacity));
    PAGES(elpis_semantic_hyperedge_v1,semantic_view_node_hyperedges(v,&node,offset,limit,out,capacity));
    PAGES(elpis_semantic_node_v1,semantic_view_enumerate_nodes_by_type(v,1,offset,limit,out,capacity));
    PAGES(elpis_semantic_hyperedge_v1,semantic_view_enumerate_hyperedges_by_type(v,1,offset,limit,out,capacity));
    PAGES(elpis_semantic_incidence_v1,semantic_view_enumerate_incidences_by_role(v,1,offset,limit,out,capacity));
    PAGES(elpis_semantic_node_v1,semantic_view_enumerate_nodes_by_authority(v,2,offset,limit,out,capacity));
    CHECK(semantic_view_node_assertions(v,&node,0,0,1,NULL,1)==0);
    CHECK(semantic_view_hyperedge_assertions(v,&edge,0,0,1,NULL,1)==0);
    CHECK(semantic_view_hyperedge_participants(v,&edge,0,1,NULL,1)==0);
    CHECK(semantic_view_node_hyperedges(v,&node,0,1,NULL,1)==0);
    CHECK(semantic_view_enumerate_nodes_by_type(v,1,0,1,NULL,1)==0);
    CHECK(semantic_view_enumerate_hyperedges_by_type(v,1,0,1,NULL,1)==0);
    CHECK(semantic_view_enumerate_incidences_by_role(v,1,0,1,NULL,1)==0);
    CHECK(semantic_view_enumerate_nodes_by_authority(v,0,0,1,NULL,1)==0);
    /* Reverse caller input: lookup and every output remain canonical. */
#define REVERSE(array, n, type) do { for(unsigned k=0;k<(n)/2;++k) { type tmp=array[k]; array[k]=array[(n)-1-k]; array[(n)-1-k]=tmp; } } while(0)
    REVERSE(nodes,7,elpis_semantic_node_v1);
    REVERSE(edges,7,elpis_semantic_hyperedge_v1);
    REVERSE(assertions,17,elpis_semantic_assertion_v1);
    REVERSE(inc,7,elpis_semantic_incidence_v1);
    REVERSE(edges[6].participants,4,elpis_semantic_participant_descriptor);
    semantic_view_set_records(v,nodes,7,assertions,17,edges,7,inc,7);
    for(unsigned i=0;i<7;++i) {
        CHECK(semantic_view_lookup_node(v,&nodes[i].node_identity));
        CHECK(semantic_view_lookup_hyperedge(v,&edges[i].hyperedge_identity));
    }
    const elpis_semantic_node_v1 *ns[7];
    CHECK(semantic_view_enumerate_nodes_by_type(v,1,0,7,ns,7)==4);
    for(unsigned i=0;i<4;++i) CHECK(ns[i]->node_identity.bytes[0]==1+2*i);
    const elpis_semantic_hyperedge_v1 *es[7];
    CHECK(semantic_view_node_hyperedges(v,&node,0,7,es,7)==4);
    for(unsigned i=0;i<4;++i) CHECK(es[i]->hyperedge_identity.bytes[0]==1+2*i);
    const elpis_semantic_assertion_v1 *as[7];
    CHECK(semantic_view_node_assertions(v,&node,2,0,7,as,7)==4);
    for(unsigned i=0;i<4;++i) CHECK(as[i]->provenance_digest.bytes[0]==1+2*i);
    CHECK(semantic_view_hyperedge_assertions(v,&edge,2,0,7,as,7)==4);
    for(unsigned i=0;i<4;++i) CHECK(as[i]->provenance_digest.bytes[0]==1+2*i);
    const elpis_semantic_incidence_v1 *is[7];
    CHECK(semantic_view_enumerate_incidences_by_role(v,1,0,7,is,7)==4);
    for(unsigned i=0;i<4;++i) CHECK(is[i]->ordinal==2*i);
    const elpis_semantic_participant_descriptor *ps[7];
    CHECK(semantic_view_hyperedge_participants(v,&edge,0,7,ps,7)==4);
    for(unsigned i=0;i<4;++i) CHECK(ps[i]->ordinal==i);
    CHECK(memcmp(semantic_view_lookup_hyperedge(v,&edge),&edges[6],sizeof(edges[6]))==0);
    const elpis_semantic_node_v1 *before=semantic_view_lookup_node(v,&node);
    semantic_view_set_records(v,NULL,1,assertions,17,edges,7,inc,7);
    CHECK(semantic_view_lookup_node(v,&node)==before);
    CHECK(semantic_view_total_nodes(v)==7 && semantic_view_total_assertions(v)==17);
#ifdef VIEW_WRAP_ALLOC
    for(int failure=0;failure<4;++failure) {
        fail_after=failure;
        semantic_view_set_records(v,nodes,7,assertions,17,edges,7,inc,7);
        fail_after=-1;
        CHECK(semantic_view_lookup_node(v,&node)==before);
        CHECK(semantic_view_total_hyperedges(v)==7 && semantic_view_total_incidences(v)==7);
    }
#endif
    edges[0].participant_count=SEMANTIC_MAX_PARTICIPANTS+1;
    semantic_view_set_records(v,nodes,7,assertions,17,edges,7,inc,7);
    CHECK(semantic_view_lookup_node(v,&node)==before);
    /* Aliased source is copied before the old storage is released. */
    semantic_view_set_records(v,before,1,NULL,0,NULL,0,NULL,0);
    CHECK(semantic_view_total_nodes(v)==1 && semantic_view_lookup_node(v,&node));
    CHECK(semantic_view_total_assertions(v)==0 && semantic_view_total_hyperedges(v)==0);
    semantic_view_set_records(v,NULL,0,NULL,0,NULL,0,NULL,0);
    CHECK(semantic_view_total_nodes(v)==0 && !semantic_view_lookup_node(v,&node));
    semantic_view_destroy(v); semantic_snapshot_destroy(m);
    puts("PASS view pagination contract"); return 0;
}
