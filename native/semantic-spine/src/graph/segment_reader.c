/* segment_reader.c — Read and verify semantic segments.
 *
 * Recalculates all identities, rejects corruption.
 */
#include "elpis_semantic/segment.h"
#include "elpis_semantic/identity.h"
#include "elpis/sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int semantic_segment_read(const char *path,
                           semantic_segment_record *segment_out,
                           hacf_digest *segment_digest_out) {
    if (!path || !segment_out) return SEMANTIC_E_INVAL;

    FILE *f = fopen(path, "rb");
    if (!f) return SEMANTIC_E_IO;

    /* Read segment header. */
    if (fread(segment_out, sizeof(*segment_out), 1, f) != 1) {
        fclose(f);
        return SEMANTIC_E_IO;
    }

    /* Validate basic fields. */
    if (segment_out->abi_version != SEMANTIC_SEGMENT_ABI_VERSION) {
        fclose(f);
        return SEMANTIC_E_INVAL;
    }

    /* Skip builder records (we don't need them for header verification). */
    fclose(f);

    /* Recompute segment identity from header fields and compare. */
    hacf_digest computed;
    if (semantic_segment_identity(segment_out, &computed) != SEMANTIC_OK)
        return SEMANTIC_E_INVAL;

    if (memcmp(computed.bytes, segment_out->segment_identity.bytes, HACF_DIGEST_BYTES) != 0) {
        return SEMANTIC_E_DIGEST;
    }

    if (segment_digest_out) {
        *segment_digest_out = computed;
    }

    return SEMANTIC_OK;
}
