#ifndef ELPIS_SEMANTIC_TRM_NATIVE_CONTRACT_H
#define ELPIS_SEMANTIC_TRM_NATIVE_CONTRACT_H

#include <stdint.h>
#include <stddef.h>

#define TRM_NATIVE_CONTRACT_ABI_VERSION 1
#define TRM_NATIVE_CONTRACT_DOMAIN "elpis.semantic.trm_native_contract.v1"
#define TRM_NATIVE_CONTRACT_DIGEST_LEN 64
#define TRM_EVIDENCE_FILE_MAX 16
#define TRM_EVIDENCE_FILE_PATH_LEN 256

typedef enum {
    TRM_EVIDENCE_DIRECTLY_EVIDENCED = 0,
    TRM_EVIDENCE_DERIVED_FROM_EXECUTABLE_CODE = 1,
    TRM_EVIDENCE_DERIVED_FROM_CHECKPOINT_METADATA = 2,
    TRM_EVIDENCE_UNKNOWN = 3,
} trm_evidence_classification_t;

typedef struct {
    uint32_t abi_version;
    char model_manifest_digest[TRM_NATIVE_CONTRACT_DIGEST_LEN];
    uint32_t native_input_rank;
    uint32_t native_input_dimensions[4];
    char native_input_dtype[16];
    char native_input_layout[32];
    char native_blank_encoding[32];
    char native_digit_class_order[64];
    char native_value_domain[32];
    char native_normalization[32];
    char native_positional_encoding[32];
    char native_mask_semantics[64];
    uint32_t native_output_rank;
    uint32_t native_output_dimensions[4];
    char native_output_dtype[16];
    char native_output_semantics[64];
    char native_decoder_policy[64];
    char native_tie_break_policy[32];
    char native_blank_output_policy[64];
    char native_training_objective[64];
    char native_recursive_input_policy[64];
    char native_recursive_target_policy[64];
    char evidence_files[TRM_EVIDENCE_FILE_MAX][TRM_EVIDENCE_FILE_PATH_LEN];
    uint32_t evidence_file_count;
    trm_evidence_classification_t field_classification[32];
    uint32_t field_count;
    char contract_confidence[32];
    char contract_digest[TRM_NATIVE_CONTRACT_DIGEST_LEN];
} trm_native_contract_t;

trm_native_contract_t trm_native_contract_create(void);
int trm_native_contract_validate(const trm_native_contract_t *contract);
void trm_native_contract_compute_digest(const trm_native_contract_t *contract);
int trm_native_contract_has_unknown_fields(const trm_native_contract_t *contract);
uint32_t trm_native_contract_unknown_field_count(const trm_native_contract_t *contract);

#endif
