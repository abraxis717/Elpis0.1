/* P10R native contract test */
#include <stdio.h>
#include <assert.h>
#include "elpis_semantic/trm_native_contract.h"

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

    /* Digest is non-empty after computation */
    trm_native_contract_compute_digest(&c);
    assert(c.contract_digest[0] != '\0');

    /* Null pointer safety */
    assert(!trm_native_contract_validate(NULL));
    assert(trm_native_contract_has_unknown_fields(NULL));
    assert(trm_native_contract_unknown_field_count(NULL) == 0);

    printf("PASS: test_native_contract\n");
    return 0;
}
