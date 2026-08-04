#include "elpis/cascade.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <string.h>

static int fails;
#define CHECK(x,msg) do{if(!(x)){fprintf(stderr,"FAIL: %s\n",msg);fails++;}}while(0)
static hacf_digest H(const char*s){hacf_digest d;elpis_sha256(s,strlen(s),d.bytes);return d;}

int main(void){
    hacf_digest schema=H("schema"),policy=H("policy"),other=H("other");
    const char payload[]="compile the fix";
    hacf_package_spec p={1,HACF_OBJ_ACTION,1,HACF_AUTH_REFERENCE,schema,policy,NULL,0,NULL,0,payload,sizeof(payload)-1};
    hacf_digest a,b;CHECK(hacf_digest_package(&p,&a)==0,"digest package");CHECK(hacf_digest_package(&p,&b)==0&&!hacf_digest_cmp(&a,&b),"digest deterministic");
    p.policy_digest=other;CHECK(hacf_digest_package(&p,&b)==0&&hacf_digest_cmp(&a,&b),"policy bound into digest");p.policy_digest=policy;

    hacf_queue*q=hacf_queue_create(8);CHECK(q!=NULL,"queue create");
    hacf_work_spec w;memset(&w,0,sizeof w);w.package=p;w.priority=5;w.safety_class=1;w.required_capabilities=4;w.required_memory_bytes=1024;
    CHECK(hacf_queue_submit(q,&w,&a)==0,"submit");CHECK(hacf_queue_submit(q,&w,&b)==1,"dedup");
    CHECK(hacf_queue_transition(q,&a,HACF_PROPOSED,HACF_SCHEMA_VALID)==0,"schema valid");
    CHECK(hacf_queue_elect(q,1,&b)==0&&!hacf_digest_cmp(&a,&b),"elect ready");
    CHECK(hacf_queue_admit(q,&a,1,0,4096,&policy)==1,"defer missing capability");
    CHECK(hacf_queue_transition(q,&a,HACF_DEFERRED,HACF_DEPENDENCIES_READY)==0,"retry deferred");
    CHECK(hacf_queue_admit(q,&a,1,4,4096,&policy)==0,"admit");
    CHECK(hacf_queue_transition(q,&a,HACF_ADMITTED,HACF_RESOURCE_LEASED)==0,"lease");
    CHECK(hacf_queue_transition(q,&a,HACF_RESOURCE_LEASED,HACF_RUNNING)==0,"run");
    CHECK(hacf_queue_transition(q,&a,HACF_RUNNING,HACF_COMMITTED)==0,"commit");
    hacf_entry_info info;CHECK(hacf_queue_get(q,&a,&info)==0&&info.state==HACF_COMMITTED,"inspect committed");

    hacf_loop_request lr={HACF_FAIL_MISSING_EVIDENCE,0,2,1};CHECK(hacf_elect_loop(&lr)==HACF_LOOP_RAG,"rag election");
    lr.failure_class=HACF_FAIL_POLICY;CHECK(hacf_elect_loop(&lr)==HACF_LOOP_REJECT,"policy rejects");
    lr.failure_class=HACF_FAIL_RUNTIME;lr.prior_attempts=2;CHECK(hacf_elect_loop(&lr)==HACF_LOOP_REJECT,"budget rejects");
    hacf_queue_destroy(q);printf("cascade checks: %s\n",fails?"FAIL":"PASS");return fails!=0;
}
