/* trm_adapter_packet.c — Immutable TRM adapter packet v1. */

#include "elpis_semantic/trm_adapter_packet.h"
#include "elpis_semantic/trm_persist.h"
#include "elpis_semantic/identity.h"
#include "elpis/cascade.h"
#include <string.h>
#include <stdint.h>

void elpis_trm_adapter_packet_init(elpis_semantic_trm_adapter_packet_v1 *packet) {
    if (!packet) return;
    memset(packet, 0, sizeof(*packet));
    packet->abi_version = TRM_ADAPTER_PACKET_VERSION;
}

int elpis_trm_adapter_packet_identity(
    const elpis_semantic_trm_adapter_packet_v1 *packet, hacf_digest *out)
{
    if (!packet || !out) return SEMANTIC_E_INVAL;
    return elpis_trm_digest_domain("elpis.semantic.trm_adapter_packet.v1",
        packet->abi_version, (const uint8_t *)packet, sizeof(*packet), out);
}

static int digest_nonzero(const hacf_digest *d) {
    if (!d) return 0;
    for (uint32_t i = 0; i < HACF_DIGEST_BYTES; i++) {
        if (d->bytes[i] != 0) return 1;
    }
    return 0;
}

int elpis_trm_adapter_packet_validate(const elpis_semantic_trm_adapter_packet_v1 *packet) {
    if (!packet) return SEMANTIC_E_INVAL;
    if (packet->abi_version != TRM_ADAPTER_PACKET_VERSION) return SEMANTIC_E_INVAL;

    /* Required non-zero digests */
    if (!digest_nonzero(&packet->P7_structural_packet_digest)) return SEMANTIC_E_INVAL;
    if (!digest_nonzero(&packet->TRM_abi_digest)) return SEMANTIC_E_INVAL;
    if (!digest_nonzero(&packet->input_tensor_digest)) return SEMANTIC_E_INVAL;
    if (!digest_nonzero(&packet->fixed_mask_digest)) return SEMANTIC_E_INVAL;
    if (!digest_nonzero(&packet->writable_mask_digest)) return SEMANTIC_E_INVAL;

    for (size_t i = 0; i < sizeof(packet->reserved); i++) {
        if (packet->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_trm_adapter_packet(const char *path, const elpis_semantic_trm_adapter_packet_v1 *packet) {
    if (!path || !packet) return SEMANTIC_E_INVAL;
    return elpis_trm_write_binary(path, (const uint8_t *)packet, (uint32_t)sizeof(*packet));
}

int elpis_read_trm_adapter_packet(const char *path, elpis_semantic_trm_adapter_packet_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    memset(out, 0, sizeof(*out));
    uint32_t actual = 0;
    int ret = elpis_trm_read_binary(path, (uint8_t *)out, (uint32_t)sizeof(*out), &actual);
    if (ret < 0) return SEMANTIC_E_IO;
    if (actual != (uint32_t)sizeof(*out)) return SEMANTIC_E_INVAL;
    return SEMANTIC_OK;
}
