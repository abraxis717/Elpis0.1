/* refinement_integration_receipt.c — Integration receipt v1. */
#include "elpis_semantic/refinement_integration_receipt.h"
#include "elpis/sha256.h"
#include "elpis_semantic/identity.h"
#include <string.h>
#include <stdio.h>

void elpis_refinement_integration_receipt_init(
    elpis_semantic_refinement_integration_receipt_v1 *r) {
    memset(r, 0, sizeof(*r));
    r->abi_version = REFINEMENT_INTEGRATION_RECEIPT_VERSION;
}

int elpis_refinement_integration_receipt_identity(
    const elpis_semantic_refinement_integration_receipt_v1 *r, hacf_digest *out) {
    const char *domain = "elpis.semantic.refinement_integration_receipt.v1";
    size_t domain_len = 50;

    uint8_t buf[1024];
    size_t off = 0;

    memcpy(buf + off, domain, domain_len); off += domain_len;
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(r->abi_version);
    memcpy(buf + off, r->request_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->policy_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->backend_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->adapter_digest.bytes, 32); off += 32;
    memcpy(buf + off, r->result_digest.bytes, 32); off += 32;
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(r->steps_executed);
    off += 4; *(uint32_t *)(buf + off - 4) = __builtin_bswap32(r->steps_bound);

    elpis_sha256(buf, off, out->bytes);
    return SEMANTIC_OK;
}

int elpis_refinement_integration_receipt_validate(
    const elpis_semantic_refinement_integration_receipt_v1 *r) {
    if (r->abi_version != REFINEMENT_INTEGRATION_RECEIPT_VERSION)
        return SEMANTIC_E_INVAL;
    if (r->execution_bounded != 1) return SEMANTIC_E_INVAL;
    if (r->all_states_sudoku_valid != 1) return SEMANTIC_E_INVAL;
    if (r->fixed_clues_unchanged != 1) return SEMANTIC_E_INVAL;
    if (r->all_changes_writable_mask != 1) return SEMANTIC_E_INVAL;
    if (r->no_direct_state_mutation != 1) return SEMANTIC_E_INVAL;
    if (r->semantic_sidecar_inaccessible != 1) return SEMANTIC_E_INVAL;
    if (r->reference_solution_inaccessible != 1) return SEMANTIC_E_INVAL;
    if (r->deterministic_execution != 1) return SEMANTIC_E_INVAL;
    if (memcmp(r->reserved, (uint8_t[64]){0}, 64) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}
