/* refiner_adapter.c — Common candidate adapter implementation. */
#include "elpis_semantic/refiner_adapter.h"
#include <string.h>

void elpis_refiner_adapter_init(elpis_semantic_refiner_adapter_v1 *adapter) {
    memset(adapter, 0, sizeof(*adapter));
    adapter->abi_version = REFINER_ADAPTER_VERSION;
}

int elpis_refiner_adapter_validate(const elpis_semantic_refiner_adapter_v1 *adapter) {
    if (adapter->abi_version != REFINER_ADAPTER_VERSION) return SEMANTIC_E_INVAL;
    if (!adapter->execute) return SEMANTIC_E_INVAL;
    if (adapter->adapter_name[0] == '\0') return SEMANTIC_E_INVAL;
    if (memcmp(adapter->reserved, (uint8_t[64]){0}, 64) != 0) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}
