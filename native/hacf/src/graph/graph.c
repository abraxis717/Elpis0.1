#include "elpis/graph.h"
#include "elpis/sha256.h"
#include <string.h>

static void u32(elpis_sha256_ctx*h,uint32_t v){uint8_t b[4]={(uint8_t)(v>>24),(uint8_t)(v>>16),(uint8_t)(v>>8),(uint8_t)v};elpis_sha256_update(h,b,4);}
static void dg(elpis_sha256_ctx*h,const hacf_digest*d){elpis_sha256_update(h,d->bytes,32);}

int hacf_graph_delta_digest(const hacf_digest*prior,const hacf_graph_op*ops,uint32_t n,hacf_digest*delta,hacf_digest*next){
    if(!prior||(!ops&&n)||!delta||!next)return-1;
    elpis_sha256_ctx h;elpis_sha256_init(&h);static const char tag[]="ELPIS-GRAPH-DELTA-V1";elpis_sha256_update(&h,tag,sizeof(tag)-1);dg(&h,prior);u32(&h,n);
    for(uint32_t i=0;i<n;++i){if(ops[i].type!=HACF_GRAPH_ADD_NODE&&ops[i].type!=HACF_GRAPH_ADD_EDGE)return-1;u32(&h,ops[i].type);u32(&h,ops[i].node_or_edge_type);dg(&h,&ops[i].subject);dg(&h,&ops[i].object);dg(&h,&ops[i].provenance);u32(&h,ops[i].authority);}
    elpis_sha256_final(&h,delta->bytes);
    elpis_sha256_init(&h);static const char stag[]="ELPIS-GRAPH-SNAPSHOT-V1";elpis_sha256_update(&h,stag,sizeof(stag)-1);dg(&h,prior);dg(&h,delta);elpis_sha256_final(&h,next->bytes);return 0;
}
