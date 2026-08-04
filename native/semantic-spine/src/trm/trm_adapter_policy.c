/* trm_adapter_policy.c — Immutable TRM adapter policy v1. */

#include "elpis_semantic/trm_adapter_policy.h"
#include "elpis_semantic/trm_persist.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_trm_adapter_policy_init(elpis_semantic_trm_adapter_policy_v1 *policy) {
    if (!policy) return;
    memset(policy, 0, sizeof(*policy));
    policy->abi_version = TRM_ADAPTER_POLICY_VERSION;
    policy->input_conversion_policy = TRM_INPUT_CONVERSION_EXACT_ONE_HOT_TO_FLOAT32;
    policy->fixed_cell_policy = TRM_FIXED_WHEN_NONZERO_OR_OCCUPIED;
    policy->writable_cell_policy = TRM_WRITABLE_WHEN_ZERO_AND_UNOCCUPIED;
    policy->candidate_decode_policy = TRM_CANDIDATE_DECODE_ARGMAX_WITHOUT_SOFTMAX;
    policy->tie_break_policy = TRM_TIE_BREAK_LOWEST_DIGIT_CLASS;
    policy->nonfinite_output_policy = TRM_NONFINITE_REJECT_COMPLETE_FRAME;
    policy->class_zero_policy = TRM_CLASS_ZERO_NO_CHANGE_FOR_WRITABLE;
    policy->proposal_application_policy = TRM_PROPOSAL_ATOMIC_COMPLETE_BOARD;
    policy->sudoku_validation_policy = TRM_SUDOKU_VALIDATION_REQUIRED;
    policy->invalid_proposal_policy = TRM_INVALID_RETURN_EXACT_INPUT_BOARD;
    policy->sidecar_isolation_policy = TRM_SIDECAR_ISOLATION_MODEL_INPUT_NUMERIC_ONLY;
    policy->maximum_changed_cells = 81;
    policy->policy_flags = TRM_POLICY_FLAG_STRICT;
}

int elpis_trm_adapter_policy_identity(const elpis_semantic_trm_adapter_policy_v1 *policy, hacf_digest *out) {
    if (!policy || !out) return SEMANTIC_E_INVAL;
    return elpis_trm_digest_domain("elpis.semantic.trm_adapter_policy.v1",
        policy->abi_version, (const uint8_t *)policy, sizeof(*policy), out);
}

static int policy_enum_known(uint32_t val) {
    return (val == 0); /* All v1 enums have single value 0 */
}

int elpis_trm_adapter_policy_validate(const elpis_semantic_trm_adapter_policy_v1 *policy) {
    if (!policy) return SEMANTIC_E_INVAL;
    if (policy->abi_version != TRM_ADAPTER_POLICY_VERSION) return SEMANTIC_E_INVAL;
    if (!policy_enum_known(policy->input_conversion_policy)) return SEMANTIC_E_INVAL;
    if (!policy_enum_known(policy->fixed_cell_policy)) return SEMANTIC_E_INVAL;
    if (!policy_enum_known(policy->writable_cell_policy)) return SEMANTIC_E_INVAL;
    if (!policy_enum_known(policy->candidate_decode_policy)) return SEMANTIC_E_INVAL;
    if (!policy_enum_known(policy->tie_break_policy)) return SEMANTIC_E_INVAL;
    if (!policy_enum_known(policy->nonfinite_output_policy)) return SEMANTIC_E_INVAL;
    if (!policy_enum_known(policy->class_zero_policy)) return SEMANTIC_E_INVAL;
    if (!policy_enum_known(policy->proposal_application_policy)) return SEMANTIC_E_INVAL;
    if (!policy_enum_known(policy->sudoku_validation_policy)) return SEMANTIC_E_INVAL;
    if (!policy_enum_known(policy->invalid_proposal_policy)) return SEMANTIC_E_INVAL;
    if (!policy_enum_known(policy->sidecar_isolation_policy)) return SEMANTIC_E_INVAL;
    if (policy->maximum_changed_cells > 81) return SEMANTIC_E_INVAL;
    if (policy->policy_flags & ~TRM_POLICY_FLAG_MASK) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(policy->reserved); i++) {
        if (policy->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_trm_adapter_policy(const char *path, const elpis_semantic_trm_adapter_policy_v1 *policy) {
    if (!path || !policy) return SEMANTIC_E_INVAL;
    return elpis_trm_write_binary(path, (const uint8_t *)policy, (uint32_t)sizeof(*policy));
}

int elpis_read_trm_adapter_policy(const char *path, elpis_semantic_trm_adapter_policy_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    memset(out, 0, sizeof(*out));
    uint32_t actual = 0;
    int ret = elpis_trm_read_binary(path, (uint8_t *)out, (uint32_t)sizeof(*out), &actual);
    if (ret < 0) return SEMANTIC_E_IO;
    if (actual != (uint32_t)sizeof(*out)) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}
