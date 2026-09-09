/* P10R native contract test */
#include <stdio.h>
#include <assert.h>
#include <string.h>
#include "elpis_semantic/trm_native_contract.h"

static int is_lower_hex64(const char digest[64]) {
    for (size_t i = 0; i < 64; ++i) {
        char c = digest[i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return 0;
    }
    return 1;
}

int main(void) {
    trm_native_contract_t c = trm_native_contract_create();

    /* ABI version */
    assert(c.abi_version == TRM_NATIVE_CONTRACT_ABI_VERSION);

    /* Input is [B, 81] int64 */
    assert(c.native_input_rank == 2);
    assert(c.native_input_dimensions[0] == 1);
    assert(c.native_input_dimensions[1] == 81);

    /* Output is [B, 81, 10] float32 */
    assert(c.native_output_rank == 3);
    assert(c.native_output_dimensions[0] == 1);
    assert(c.native_output_dimensions[1] == 81);
    assert(c.native_output_dimensions[2] == 10);

    /* Validate succeeds */
    assert(trm_native_contract_validate(&c));

    /* No unknown fields by default */
    assert(!trm_native_contract_has_unknown_fields(&c));
    assert(trm_native_contract_unknown_field_count(&c) == 0);

    /* Successor digest is fixed-width, complete, and idempotent. */
    trm_native_contract_compute_digest(&c);
    assert(is_lower_hex64(c.contract_digest));
    char first_digest[TRM_NATIVE_CONTRACT_DIGEST_LEN];
    memcpy(first_digest, c.contract_digest, sizeof(first_digest));
    trm_native_contract_compute_digest(&c);
    assert(memcmp(first_digest, c.contract_digest, sizeof(first_digest)) == 0);

    /* Null pointer safety */
    assert(!trm_native_contract_validate(NULL));
    assert(trm_native_contract_has_unknown_fields(NULL));
    assert(trm_native_contract_unknown_field_count(NULL) == 0);

    printf("PASS: test_native_contract\n");
    return 0;
}
