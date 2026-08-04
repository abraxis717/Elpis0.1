#include "elpis/graph.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>
static hacf_digest H(const char*s){hacf_digest d;elpis_sha256(s,strlen(s),d.bytes);return d;}
int main(void){
    hacf_digest zero={{0}},d1,s1,d2,s2;hacf_graph_op ops[2];memset(ops,0,sizeof ops);
    ops[0].type=HACF_GRAPH_ADD_NODE;ops[0].node_or_edge_type=1;ops[0].subject=H("claim");ops[0].provenance=H("source");ops[0].authority=HACF_AUTH_REFERENCE;
    ops[1].type=HACF_GRAPH_ADD_EDGE;ops[1].node_or_edge_type=7;ops[1].subject=H("claim");ops[1].object=H("failure");ops[1].provenance=H("decision");ops[1].authority=HACF_AUTH_REFERENCE;
    if(hacf_graph_delta_digest(&zero,ops,2,&d1,&s1)!=0)return 1;
    if(hacf_graph_delta_digest(&zero,ops,2,&d2,&s2)!=0)return 1;
    if(hacf_digest_cmp(&d1,&d2)||hacf_digest_cmp(&s1,&s2))return 1;
    ops[1].authority=HACF_AUTH_ADVISORY;
    if(hacf_graph_delta_digest(&zero,ops,2,&d2,&s2)!=0||!hacf_digest_cmp(&d1,&d2))return 1;
    puts("graph checks: PASS");return 0;
}
