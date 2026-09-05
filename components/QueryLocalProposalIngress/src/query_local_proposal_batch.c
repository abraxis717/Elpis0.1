#include "query_local_proposal_batch.h"
#include "elpis/sha256.h"

#include <arpa/inet.h>
#include <stdlib.h>
#include <string.h>

typedef struct prepared_record {
    elpis_query_local_proposal_v1 proposal;
    elpis_semantic_node_v1 node;
    elpis_semantic_assertion_v1 assertion;
    elpis_query_local_representation_receipt_v1 individual_receipt;
} prepared_record;

static int digest_eq(const hacf_digest *a, const hacf_digest *b) {
    return memcmp(a->bytes, b->bytes, HACF_DIGEST_BYTES) == 0;
}

static int zero_bytes(const uint8_t *p, size_t n) {
    for (size_t i=0; i<n; ++i) if (p[i] != 0) return 0;
    return 1;
}

static void put_u32(elpis_sha256_ctx *ctx, uint32_t v) {
    uint32_t be=htonl(v);
    elpis_sha256_update(ctx,&be,4);
}

static void put_domain(elpis_sha256_ctx *ctx, const char *domain) {
    put_u32(ctx,(uint32_t)strlen(domain));
    elpis_sha256_update(ctx,domain,strlen(domain));
}

static int proposal_cmp(const void *va, const void *vb) {
    const prepared_record *a=(const prepared_record *)va;
    const prepared_record *b=(const prepared_record *)vb;
    return memcmp(a->proposal.envelope_identity.bytes,
                  b->proposal.envelope_identity.bytes,
                  HACF_DIGEST_BYTES);
}

static int batch_receipt_identity(
    const elpis_query_local_proposal_batch_receipt_v1 *r,
    hacf_digest *out)
{
    if(!r||!out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    put_domain(&ctx,"elpis.semantic.query_local_proposal_batch_receipt.v1");
    put_u32(&ctx,r->abi_version);
    elpis_sha256_update(&ctx,r->query_digest.bytes,HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx,r->proposal_digest.bytes,HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx,r->proposal_set_digest.bytes,HACF_DIGEST_BYTES);
    put_u32(&ctx,r->proposal_count);
    elpis_sha256_update(&ctx,r->registry_contract_digest.bytes,HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx,r->native_registry_digest.bytes,HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx,r->representation_policy_digest.bytes,HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx,r->hacf_corpus_manifest_digest.bytes,HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx,r->hacf_context_graph_manifest_digest.bytes,HACF_DIGEST_BYTES);
    elpis_sha256_update(&ctx,r->overlay_identity.bytes,HACF_DIGEST_BYTES);
    put_u32(&ctx,r->disposition);
    put_u32(&ctx,r->semantic_authority);
    put_u32(&ctx,r->admission_authority);
    put_u32(&ctx,r->execution_authority);
    put_u32(&ctx,r->runtime_admission);
    elpis_sha256_final(&ctx,out->bytes);
    return SEMANTIC_OK;
}

int elpis_query_local_proposal_batch_receipt_validate(
    const elpis_query_local_proposal_batch_receipt_v1 *r)
{
    if(!r) return SEMANTIC_E_INVAL;
    if(r->abi_version != ELPIS_QUERY_LOCAL_PROPOSAL_BATCH_RECEIPT_ABI_VERSION)
        return SEMANTIC_E_INVAL;
    if(r->proposal_count == 0 || r->proposal_count > ELPIS_QUERY_LOCAL_PROPOSAL_MAX_BATCH)
        return SEMANTIC_E_CARDINALITY;
    if(r->disposition != ELPIS_QUERY_LOCAL_PROPOSAL_BATCH_RECEIPT_COMMITTED)
        return SEMANTIC_E_INVAL;
    if(r->semantic_authority || r->admission_authority ||
       r->execution_authority || r->runtime_admission)
        return SEMANTIC_E_AUTHORITY;
    if(!zero_bytes(r->reserved,sizeof r->reserved))
        return SEMANTIC_E_INVAL;
    hacf_digest expected;
    if(batch_receipt_identity(r,&expected)!=SEMANTIC_OK)
        return SEMANTIC_E_DIGEST;
    return digest_eq(&expected,&r->receipt_identity) ? SEMANTIC_OK : SEMANTIC_E_DIGEST;
}

int elpis_query_local_proposal_set_digest(
    const elpis_query_local_proposal_v1 *proposals,
    uint32_t proposal_count,
    hacf_digest *out)
{
    if(!proposals||!out) return SEMANTIC_E_INVAL;
    if(proposal_count==0 || proposal_count>ELPIS_QUERY_LOCAL_PROPOSAL_MAX_BATCH)
        return SEMANTIC_E_CARDINALITY;

    hacf_digest *ids=calloc(proposal_count,sizeof(*ids));
    if(!ids) return SEMANTIC_E_NOMEM;
    for(uint32_t i=0;i<proposal_count;++i)
        ids[i]=proposals[i].envelope_identity;

    for(uint32_t i=1;i<proposal_count;++i) {
        hacf_digest x=ids[i];
        uint32_t j=i;
        while(j && memcmp(x.bytes,ids[j-1].bytes,HACF_DIGEST_BYTES)<0) {
            ids[j]=ids[j-1];
            --j;
        }
        ids[j]=x;
    }

    for(uint32_t i=1;i<proposal_count;++i) {
        if(digest_eq(&ids[i-1],&ids[i])) {
            free(ids);
            return SEMANTIC_E_DUPLICATE;
        }
    }

    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    put_domain(&ctx,"elpis.semantic.query_local_proposal_set.v1");
    put_u32(&ctx,ELPIS_QUERY_LOCAL_PROPOSAL_BATCH_ABI_VERSION);
    put_u32(&ctx,proposal_count);
    for(uint32_t i=0;i<proposal_count;++i)
        elpis_sha256_update(&ctx,ids[i].bytes,HACF_DIGEST_BYTES);
    elpis_sha256_final(&ctx,out->bytes);
    free(ids);
    return SEMANTIC_OK;
}

int elpis_query_local_proposal_batch_build_overlay(
    const semantic_snapshot_manifest *base_manifest,
    const semantic_type_registry *registry,
    const elpis_query_local_context_v1 *context,
    const elpis_query_local_proposal_v1 *proposals,
    uint32_t proposal_count,
    semantic_query_overlay **overlay_out,
    elpis_query_local_proposal_batch_receipt_v1 *receipt_out)
{
    if(overlay_out) *overlay_out=NULL;
    if(receipt_out) memset(receipt_out,0,sizeof *receipt_out);

    if(!base_manifest||!registry||!context||!proposals||!overlay_out||!receipt_out)
        return SEMANTIC_E_INVAL;
    if(proposal_count==0 || proposal_count>ELPIS_QUERY_LOCAL_PROPOSAL_MAX_BATCH)
        return SEMANTIC_E_CARDINALITY;

    prepared_record *prepared=calloc(proposal_count,sizeof(*prepared));
    if(!prepared) return SEMANTIC_E_NOMEM;

    int rc=SEMANTIC_OK;
    for(uint32_t i=0;i<proposal_count;++i) {
        prepared[i].proposal=proposals[i];
        rc=elpis_query_local_proposal_validate(&prepared[i].proposal,context);
        if(rc!=SEMANTIC_OK) goto fail;
        rc=elpis_query_local_proposal_materialize(
            &prepared[i].proposal,context,
            &prepared[i].node,&prepared[i].assertion,
            &prepared[i].individual_receipt);
        if(rc!=SEMANTIC_OK) goto fail;
    }

    qsort(prepared,proposal_count,sizeof(*prepared),proposal_cmp);
    for(uint32_t i=1;i<proposal_count;++i) {
        if(digest_eq(&prepared[i-1].proposal.envelope_identity,
                     &prepared[i].proposal.envelope_identity)) {
            rc=SEMANTIC_E_DUPLICATE;
            goto fail;
        }
    }

    hacf_digest set_digest;
    elpis_query_local_proposal_v1 *sorted_props=
        calloc(proposal_count,sizeof(*sorted_props));
    if(!sorted_props) {
        rc=SEMANTIC_E_NOMEM;
        goto fail;
    }
    for(uint32_t i=0;i<proposal_count;++i)
        sorted_props[i]=prepared[i].proposal;
    rc=elpis_query_local_proposal_set_digest(sorted_props,proposal_count,&set_digest);
    free(sorted_props);
    if(rc!=SEMANTIC_OK) goto fail;

    semantic_query_overlay *overlay=
        semantic_overlay_create(base_manifest,registry,&context->query_digest);
    if(!overlay) {
        rc=SEMANTIC_E_NOMEM;
        goto fail;
    }

    rc=elpis_query_local_overlay_bind_context(overlay,registry,context);
    if(rc!=SEMANTIC_OK) {
        semantic_overlay_destroy(overlay);
        goto fail;
    }

    for(uint32_t i=0;i<proposal_count;++i) {
        rc=semantic_overlay_add_node(overlay,&prepared[i].node);
        if(rc!=SEMANTIC_BUILDER_OK) {
            semantic_overlay_destroy(overlay);
            goto fail;
        }
        rc=semantic_overlay_add_assertion(overlay,&prepared[i].assertion);
        if(rc!=SEMANTIC_BUILDER_OK) {
            semantic_overlay_destroy(overlay);
            goto fail;
        }
    }

    rc=semantic_overlay_finalize(overlay);
    if(rc!=SEMANTIC_OK) {
        semantic_overlay_destroy(overlay);
        goto fail;
    }

    elpis_query_local_proposal_batch_receipt_v1 receipt;
    memset(&receipt,0,sizeof receipt);
    receipt.abi_version=ELPIS_QUERY_LOCAL_PROPOSAL_BATCH_RECEIPT_ABI_VERSION;
    receipt.query_digest=context->query_digest;
    receipt.proposal_digest=context->proposal_digest;
    receipt.proposal_set_digest=set_digest;
    receipt.proposal_count=proposal_count;
    receipt.registry_contract_digest=context->registry_contract_digest;
    receipt.native_registry_digest=context->native_registry_digest;
    receipt.representation_policy_digest=context->representation_policy_digest;
    receipt.hacf_corpus_manifest_digest=context->hacf_corpus_manifest_digest;
    receipt.hacf_context_graph_manifest_digest=context->hacf_context_graph_manifest_digest;
    receipt.overlay_identity=overlay->overlay_identity;
    receipt.disposition=ELPIS_QUERY_LOCAL_PROPOSAL_BATCH_RECEIPT_COMMITTED;

    rc=batch_receipt_identity(&receipt,&receipt.receipt_identity);
    if(rc!=SEMANTIC_OK ||
       elpis_query_local_proposal_batch_receipt_validate(&receipt)!=SEMANTIC_OK) {
        semantic_overlay_destroy(overlay);
        rc=SEMANTIC_E_DIGEST;
        goto fail;
    }

    *receipt_out=receipt;
    *overlay_out=overlay;
    free(prepared);
    return SEMANTIC_OK;

fail:
    free(prepared);
    *overlay_out=NULL;
    memset(receipt_out,0,sizeof *receipt_out);
    return rc;
}
