#include "elpis_semantic/trm_native_contract.h"
#include <string.h>
#include <stdio.h>
#include <openssl/sha.h>

static void sha256_hex(const void *data, size_t len, char *out, size_t out_len) {
    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256(data, len, hash);
    for (int i = 0; i < SHA256_DIGEST_LENGTH && (size_t)(i * 2 + 2) < out_len; i++) {
        sprintf(out + i * 2, "%02x", hash[i]);
    }
}

trm_native_contract_t trm_native_contract_create(void) {
    trm_native_contract_t contract;
    memset(&contract, 0, sizeof(contract));
    contract.abi_version = TRM_NATIVE_CONTRACT_ABI_VERSION;
    contract.native_input_rank = 2;
    contract.native_input_dimensions[0] = 1;
    contract.native_input_dimensions[1] = 81;
    strncpy(contract.native_input_dtype, "INT64", sizeof(contract.native_input_dtype) - 1);
    strncpy(contract.native_input_layout, "ROW_MAJOR_CONTIGUOUS", sizeof(contract.native_input_layout) - 1);
    strncpy(contract.native_blank_encoding, "CLASS_ZERO_IS_BLANK", sizeof(contract.native_blank_encoding) - 1);
    strncpy(contract.native_digit_class_order, "CLASSES_1_TO_9_FOR_DIGITS_1_TO_9", sizeof(contract.native_digit_class_order) - 1);
    strncpy(contract.native_value_domain, "0_TO_9_INCLUSIVE", sizeof(contract.native_value_domain) - 1);
    strncpy(contract.native_normalization, "NONE_INTEGER_INPUT", sizeof(contract.native_normalization) - 1);
    strncpy(contract.native_positional_encoding, "ROPE_THETA_10000", sizeof(contract.native_positional_encoding) - 1);
    strncpy(contract.native_mask_semantics, "NO_EXPLICIT_MASK_BLANK_IS_CLASS_ZERO", sizeof(contract.native_mask_semantics) - 1);
    contract.native_output_rank = 3;
    contract.native_output_dimensions[0] = 1;
    contract.native_output_dimensions[1] = 81;
    contract.native_output_dimensions[2] = 10;
    strncpy(contract.native_output_dtype, "FLOAT32", sizeof(contract.native_output_dtype) - 1);
    strncpy(contract.native_output_semantics, "LOGITS_UNNORMALIZED_DIGIT_CLASS_SCORES", sizeof(contract.native_output_semantics) - 1);
    strncpy(contract.native_decoder_policy, "ARGMAX_PER_CELL_LOWEST_CLASS_TIEBREAK", sizeof(contract.native_decoder_policy) - 1);
    strncpy(contract.native_tie_break_policy, "LOWEST_CLASS", sizeof(contract.native_tie_break_policy) - 1);
    strncpy(contract.native_blank_output_policy, "CLASS_ZERO_MEANS_PREDICT_BLANK", sizeof(contract.native_blank_output_policy) - 1);
    strncpy(contract.native_training_objective, "CROSS_ENTROPY_DENOSING_AUTOENCODER", sizeof(contract.native_training_objective) - 1);
    strncpy(contract.native_recursive_input_policy, "FULL_BOARD_EACH_STEP", sizeof(contract.native_recursive_input_policy) - 1);
    strncpy(contract.native_recursive_target_policy, "COMPLETE_GRID_TARGET", sizeof(contract.native_recursive_target_policy) - 1);
    contract.evidence_file_count = 0;
    contract.field_count = 0;
    strncpy(contract.contract_confidence, "HIGH_ALL_FIELDS_EVIDENCED", sizeof(contract.contract_confidence) - 1);
    contract.contract_digest[0] = '\0';
    return contract;
}

int trm_native_contract_validate(const trm_native_contract_t *contract) {
    if (!contract) return 0;
    if (contract->abi_version != TRM_NATIVE_CONTRACT_ABI_VERSION) return 0;
    if (contract->native_input_rank != 2) return 0;
    if (contract->native_output_rank != 3) return 0;
    return 1;
}

void trm_native_contract_compute_digest(const trm_native_contract_t *contract) {
    if (!contract) return;
    sha256_hex(contract, sizeof(trm_native_contract_t),
               contract->contract_digest, TRM_NATIVE_CONTRACT_DIGEST_LEN);
}

int trm_native_contract_has_unknown_fields(const trm_native_contract_t *contract) {
    if (!contract) return 1;
    for (uint32_t i = 0; i < contract->field_count; i++) {
        if (contract->field_classification[i] == TRM_EVIDENCE_UNKNOWN) return 1;
    }
    return 0;
}

uint32_t trm_native_contract_unknown_field_count(const trm_native_contract_t *contract) {
    if (!contract) return 0;
    uint32_t count = 0;
    for (uint32_t i = 0; i < contract->field_count; i++) {
        if (contract->field_classification[i] == TRM_EVIDENCE_UNKNOWN) count++;
    }
    return count;
}
