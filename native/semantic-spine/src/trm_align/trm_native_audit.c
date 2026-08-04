#include "elpis_semantic/trm_native_contract.h"
#include <stdio.h>

/* Native contract audit: verify all fields are classified. */
int trm_native_audit_check(const trm_native_contract_t *contract) {
    if (!contract) return 0;
    if (!trm_native_contract_validate(contract)) return 0;
    if (trm_native_contract_has_unknown_fields(contract)) return 0;
    return 1;
}
