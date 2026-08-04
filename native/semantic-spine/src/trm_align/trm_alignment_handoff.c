#include "elpis_semantic/trm_alignment_handoff.h"
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

trm_alignment_handoff_t trm_alignment_handoff_create(void) {
    trm_alignment_handoff_t handoff;
    memset(&handoff, 0, sizeof(handoff));
    handoff.abi_version = 1;
    handoff.handoff_kind = TRM_HANDOFF_FROZEN_TRM_ALIGNMENT_DIAGNOSIS;
    handoff.p10_negative_result_unchanged = 1;
    handoff.frozen_model_unchanged = 1;
    handoff.no_weights_changed = 1;
    handoff.no_training = 1;
    handoff.runtime_admission = 0;
    strncpy(handoff.p10r_statement,
            "P10 remains measured-not-efficacious. P10R does not retroactively qualify the frozen TRM. "
            "Diagnostic adapters are non-production artifacts. No model weights were changed. "
            "No semantic relation was changed. No authority value was changed. "
            "No projector target is qualified. No residual81 definition exists. "
            "Runtime admission remains false.",
            TRM_HANDOFF_STATEMENT_LEN - 1);
    return handoff;
}

void trm_alignment_handoff_compute_digest(trm_alignment_handoff_t *handoff) {
    if (!handoff) return;
    sha256_hex(handoff, sizeof(trm_alignment_handoff_t),
               handoff->handoff_digest, TRM_HANDOFF_DIGEST_LEN);
}

int trm_alignment_handoff_validate(const trm_alignment_handoff_t *handoff) {
    if (!handoff) return 0;
    if (handoff->abi_version != 1) return 0;
    if (handoff->handoff_kind != TRM_HANDOFF_FROZEN_TRM_ALIGNMENT_DIAGNOSIS) return 0;
    if (handoff->runtime_admission != 0) return 0;
    if (handoff->no_weights_changed != 1) return 0;
    if (handoff->no_training != 1) return 0;
    return 1;
}
