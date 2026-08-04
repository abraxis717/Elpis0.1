/* elpis_semantic/evidence_typer_profile.h — Evidence-typer provider profile.
 *
 * Records how a typing proposal was produced. Contains NO runtime handle,
 * model path, network endpoint, or mutable state. The profile is immutable
 * metadata only — P4 does not execute any provider.
 *
 * Identity domain: "elpis.semantic.evidence_typer_profile.v1"
 */
#ifndef ELPIS_SEMANTIC_EVIDENCE_TYPER_PROFILE_H
#define ELPIS_SEMANTIC_EVIDENCE_TYPER_PROFILE_H

#include "elpis/cascade.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EVIDENCE_TYPER_PROFILE_ABI_VERSION 1u

/* Provider kinds — proposal source classification */
typedef enum evidence_typer_provider_kind {
    TYPER_KIND_DETERMINISTIC_RULE  = 1u,
    TYPER_KIND_EXTERNAL_MODEL      = 2u,
    TYPER_KIND_MANUAL_CURATED      = 3u,
    TYPER_KIND_IMPORTED_SEALED     = 4u
} evidence_typer_provider_kind;

/* Provider flags */
#define TYPER_FLAG_NONE     0u
#define TYPER_FLAG_BATCH    0x01u   /* produces batch proposals */
#define TYPER_FLAG_STREAM   0x02u   /* produces streaming proposals */
#define TYPER_FLAG_MASK     0x03u

typedef struct elpis_evidence_typer_profile_v1 {
    uint32_t                            abi_version;
    evidence_typer_provider_kind        provider_kind;
    hacf_digest                         provider_identity_digest;
    hacf_digest                         provider_code_digest;
    hacf_digest                         provider_configuration_digest;
    hacf_digest                         input_schema_digest;
    hacf_digest                         output_schema_digest;
    hacf_digest                         normalization_policy_digest;
    uint32_t                            confidence_scale;      /* positive integer */
    uint32_t                            maximum_claims_per_item;
    uint32_t                            maximum_relations_per_item;
    hacf_digest                         determinism_declaration; /* metadata only */
    uint32_t                            provider_flags;
    hacf_digest                         profile_identity;
    uint8_t                             reserved[48];
} elpis_evidence_typer_profile_v1;

/* Zero-initialize and set abi_version */
void elpis_typer_profile_init(elpis_evidence_typer_profile_v1 *profile);

/* Compute profile identity.
 * Domain: "elpis.semantic.evidence_typer_profile.v1"
 * Byte stream: domain_tag || abi_version(4 BE) || provider_kind(4 BE)
 *             || provider_identity_digest(32) || provider_code_digest(32)
 *             || provider_configuration_digest(32) || input_schema_digest(32)
 *             || output_schema_digest(32) || normalization_policy_digest(32)
 *             || confidence_scale(4 BE) || maximum_claims_per_item(4 BE)
 *             || maximum_relations_per_item(4 BE) || determinism_declaration(32)
 *             || provider_flags(4 BE). */
int elpis_typer_profile_identity(const elpis_evidence_typer_profile_v1 *profile, hacf_digest *out);

/* Validate: allowed kind, positive confidence scale, nonzero bounded max counts,
 * zero reserved fields, known ABI version. */
int elpis_typer_profile_validate(const elpis_evidence_typer_profile_v1 *profile);

/* Compare profiles by identity digest */
int elpis_typer_profile_cmp(const elpis_evidence_typer_profile_v1 *a,
                            const elpis_evidence_typer_profile_v1 *b);

#ifdef __cplusplus
}
#endif
#endif
