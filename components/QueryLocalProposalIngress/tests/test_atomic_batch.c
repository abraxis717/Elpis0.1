#include "query_local_proposal_batch.h"
#include "elpis/sha256.h"
#include "fixture.h"

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static hacf_digest D(const unsigned char x[32]) {
    hacf_digest d; memcpy(d.bytes,x,32); return d;
}
static int deq(const hacf_digest *a,const hacf_digest *b) {
    return memcmp(a->bytes,b->bytes,HACF_DIGEST_BYTES)==0;
}
static int bytes_zero(const void *p,size_t n) {
    const unsigned char *b=(const unsigned char *)p;
    for(size_t i=0;i<n;++i) if(b[i]!=0) return 0;
    return 1;
}
static void hx(const hacf_digest *d,char out[65]) {
    static const char h[]="0123456789abcdef";
    for(unsigned i=0;i<32;++i) {
        out[2*i]=h[d->bytes[i]>>4];
        out[2*i+1]=h[d->bytes[i]&15];
    }
    out[64]=0;
}

static semantic_type_registry *registry_make(void) {
    semantic_type_registry *r=semantic_type_registry_create();
    if(!r) return NULL;
    semantic_node_type_entry n;
    memset(&n,0,sizeof n);
    n.node_type=ELPIS_QUERY_LOCAL_PROPOSAL_NODE_TYPE;
    n.semantic_flag_mask=SEMANTIC_NODE_FLAG_EXTERNAL;
    n.min_authority=0;
    n.max_authority=0;
    if(semantic_type_registry_add_node_type(r,&n)!=SEMANTIC_OK) {
        semantic_type_registry_destroy(r); return NULL;
    }
    if(semantic_type_registry_seal(r,NULL)!=SEMANTIC_OK) {
        semantic_type_registry_destroy(r); return NULL;
    }
    return r;
}

static void context_make(elpis_query_local_context_v1 *c) {
    memset(c,0,sizeof *c);
    c->query_digest=D(FIX_QUERY_DIGEST);
    c->proposal_digest=D(FIX_PROPOSAL_DIGEST);
    c->hacf_corpus_manifest_digest=D(FIX_HACF_CORPUS_DIGEST);
    c->hacf_context_graph_manifest_digest=D(FIX_HACF_GRAPH_DIGEST);
    c->registry_contract_digest=D(FIX_REGISTRY_CONTRACT_DIGEST);
    c->native_registry_digest=D(FIX_NATIVE_REGISTRY_DIGEST);
    c->representation_policy_digest=D(FIX_POLICY_DIGEST);
}

static void proposal_make(elpis_query_local_proposal_v1 *p,
                          const elpis_query_local_context_v1 *c,
                          const unsigned char candidate[32]) {
    memset(p,0,sizeof *p);
    p->abi_version=ELPIS_QUERY_LOCAL_PROPOSAL_ABI_VERSION;
    p->query_digest=c->query_digest;
    p->proposal_digest=c->proposal_digest;
    p->candidate_digest=D(candidate);
    p->hacf_corpus_manifest_digest=c->hacf_corpus_manifest_digest;
    p->hacf_context_graph_manifest_digest=c->hacf_context_graph_manifest_digest;
    p->registry_contract_digest=c->registry_contract_digest;
    p->native_registry_digest=c->native_registry_digest;
    p->representation_policy_digest=c->representation_policy_digest;
    p->candidate_status=ELPIS_QUERY_LOCAL_PROPOSAL_STATUS_PROPOSED_UNADMITTED;
    if(elpis_query_local_proposal_identity(p,&p->envelope_identity)!=SEMANTIC_OK) abort();
}

static semantic_snapshot_manifest base_make(void) {
    semantic_snapshot_manifest b;
    memset(&b,0,sizeof b);
    b.abi_version=SEMANTIC_SNAPSHOT_ABI_VERSION;
    elpis_sha256("qlp-atomic-batch-base",strlen("qlp-atomic-batch-base"),b.manifest_digest.bytes);
    b.hacf_graph_snapshot_digest=D(FIX_HACF_GRAPH_DIGEST);
    return b;
}

static int failure_is_atomic(
    const semantic_snapshot_manifest *base,
    const semantic_type_registry *registry,
    const elpis_query_local_context_v1 *ctx,
    const elpis_query_local_proposal_v1 *props,
    uint32_t count)
{
    semantic_query_overlay *out=(semantic_query_overlay *)(uintptr_t)1u;
    elpis_query_local_proposal_batch_receipt_v1 receipt;
    memset(&receipt,0xA5,sizeof receipt);
    int rc=elpis_query_local_proposal_batch_build_overlay(
        base,registry,ctx,props,count,&out,&receipt);
    if(rc==SEMANTIC_OK) {
        if(out) semantic_overlay_destroy(out);
        return 0;
    }
    return out==NULL && bytes_zero(&receipt,sizeof receipt);
}

int main(void) {
    if(FIX_CANDIDATE_COUNT != 2u) return 2;

    semantic_type_registry *registry=registry_make();
    if(!registry) return 3;
    hacf_digest rd;
    if(semantic_type_registry_digest(registry,&rd)!=SEMANTIC_OK ||
       !deq(&rd,(const hacf_digest *)FIX_NATIVE_REGISTRY_DIGEST))
        return 4;

    elpis_query_local_context_v1 ctx;
    context_make(&ctx);
    semantic_snapshot_manifest base=base_make();

    elpis_query_local_proposal_v1 props[2];
    proposal_make(&props[0],&ctx,FIX_CANDIDATE_IDS[0]);
    proposal_make(&props[1],&ctx,FIX_CANDIDATE_IDS[1]);

    semantic_query_overlay *a=NULL,*rev=NULL,*mut=NULL;
    elpis_query_local_proposal_batch_receipt_v1 ra,rr,rm;

    if(elpis_query_local_proposal_batch_build_overlay(
           &base,registry,&ctx,props,2,&a,&ra)!=SEMANTIC_OK) return 5;
    if(!a || elpis_query_local_proposal_batch_receipt_validate(&ra)!=SEMANTIC_OK) return 6;

    elpis_query_local_proposal_v1 reversed[2]={props[1],props[0]};
    if(elpis_query_local_proposal_batch_build_overlay(
           &base,registry,&ctx,reversed,2,&rev,&rr)!=SEMANTIC_OK) return 7;

    int reverse_stable=
        deq(&a->overlay_identity,&rev->overlay_identity) &&
        deq(&a->query_local_segment_digest,&rev->query_local_segment_digest) &&
        deq(&ra.proposal_set_digest,&rr.proposal_set_digest) &&
        deq(&ra.receipt_identity,&rr.receipt_identity);

    elpis_query_local_proposal_v1 changed[2]={props[0],props[1]};
    changed[0].candidate_digest.bytes[0]^=0x80u;
    if(elpis_query_local_proposal_identity(
           &changed[0],&changed[0].envelope_identity)!=SEMANTIC_OK) return 8;
    if(elpis_query_local_proposal_batch_build_overlay(
           &base,registry,&ctx,changed,2,&mut,&rm)!=SEMANTIC_OK) return 9;

    int content_sensitive=
        !deq(&a->overlay_identity,&mut->overlay_identity) &&
        !deq(&a->query_local_segment_digest,&mut->query_local_segment_digest) &&
        !deq(&ra.proposal_set_digest,&rm.proposal_set_digest) &&
        !deq(&ra.receipt_identity,&rm.receipt_identity);

    int atomic_corrupt_envelope;
    elpis_query_local_proposal_v1 bad_env[2]={props[0],props[1]};
    bad_env[1].envelope_identity.bytes[0]^=1u;
    atomic_corrupt_envelope=failure_is_atomic(&base,registry,&ctx,bad_env,2);

    int atomic_authority;
    elpis_query_local_proposal_v1 bad_auth[2]={props[0],props[1]};
    bad_auth[1].semantic_authority=1u;
    if(elpis_query_local_proposal_identity(
           &bad_auth[1],&bad_auth[1].envelope_identity)!=SEMANTIC_OK) return 10;
    atomic_authority=failure_is_atomic(&base,registry,&ctx,bad_auth,2);

    int atomic_duplicate;
    elpis_query_local_proposal_v1 duplicate[2]={props[0],props[0]};
    atomic_duplicate=failure_is_atomic(&base,registry,&ctx,duplicate,2);

    elpis_query_local_context_v1 wrong_ctx=ctx;
    wrong_ctx.query_digest.bytes[0]^=1u;
    int atomic_wrong_context=failure_is_atomic(&base,registry,&wrong_ctx,props,2);

    int atomic_zero_count=failure_is_atomic(&base,registry,&ctx,props,0);
    int atomic_over_bound=failure_is_atomic(
        &base,registry,&ctx,props,ELPIS_QUERY_LOCAL_PROPOSAL_MAX_BATCH+1u);

    elpis_query_local_proposal_batch_receipt_v1 tampered=ra;
    tampered.overlay_identity.bytes[0]^=1u;
    int receipt_integrity=
        elpis_query_local_proposal_batch_receipt_validate(&tampered)!=SEMANTIC_OK;

    int authorities_zero=
        ra.semantic_authority==0u &&
        ra.admission_authority==0u &&
        ra.execution_authority==0u &&
        ra.runtime_admission==0u;

    int atomic_matrix=
        atomic_corrupt_envelope && atomic_authority && atomic_duplicate &&
        atomic_wrong_context && atomic_zero_count && atomic_over_bound;

    char sethex[65],overlayhex[65],receipthex[65];
    hx(&ra.proposal_set_digest,sethex);
    hx(&ra.overlay_identity,overlayhex);
    hx(&ra.receipt_identity,receipthex);

    printf("candidate_count=%u\n",ra.proposal_count);
    printf("proposal_set_digest=%s\n",sethex);
    printf("overlay_identity=%s\n",overlayhex);
    printf("batch_receipt_identity=%s\n",receipthex);
    printf("reverse_input_stable=%s\n",reverse_stable?"true":"false");
    printf("same_count_candidate_content_sensitive=%s\n",content_sensitive?"true":"false");
    printf("atomic_invalid_second_envelope=%s\n",atomic_corrupt_envelope?"PASS":"FAIL");
    printf("atomic_invalid_second_authority=%s\n",atomic_authority?"PASS":"FAIL");
    printf("atomic_duplicate_rejection=%s\n",atomic_duplicate?"PASS":"FAIL");
    printf("atomic_wrong_context=%s\n",atomic_wrong_context?"PASS":"FAIL");
    printf("atomic_zero_count=%s\n",atomic_zero_count?"PASS":"FAIL");
    printf("atomic_over_bound=%s\n",atomic_over_bound?"PASS":"FAIL");
    printf("atomic_failure_matrix=%s\n",atomic_matrix?"PASS":"FAIL");
    printf("receipt_integrity_control=%s\n",receipt_integrity?"PASS":"FAIL");
    printf("semantic_authority=%s\n",authorities_zero?"false":"true");
    printf("admission_authority=%s\n",authorities_zero?"false":"true");
    printf("execution_authority=%s\n",authorities_zero?"false":"true");
    printf("runtime_admission=%s\n",authorities_zero?"false":"true");
    printf("p4_evidence_bundle=false\n");
    printf("r3_retrieval_bundle=false\n");
    printf("grid81_mapping=false\n");

    int pass=reverse_stable && content_sensitive && atomic_matrix &&
             receipt_integrity && authorities_zero;
    printf("verdict=%s\n",pass?
        "PASS_ATOMIC_QUERY_LOCAL_PROPOSAL_BATCH_INGRESS_R1":
        "FAIL_ATOMIC_QUERY_LOCAL_PROPOSAL_BATCH_INGRESS_R1");

    semantic_overlay_destroy(a);
    semantic_overlay_destroy(rev);
    semantic_overlay_destroy(mut);
    semantic_type_registry_destroy(registry);
    return pass?0:30;
}
