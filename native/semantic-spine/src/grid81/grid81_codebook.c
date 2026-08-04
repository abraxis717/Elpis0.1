/* grid81_codebook.c — Fixed semantic-to-column codebook v1. */
#include "elpis_semantic/grid81_codebook.h"
#include <unistd.h>
#include <fcntl.h>
#include "elpis/sha256.h"
#include "elpis/cascade.h"
#include <string.h>

void elpis_grid81_codebook_init(elpis_semantic_grid81_codebook_v1 *codebook) {
    if (!codebook) return;
    memset(codebook, 0, sizeof(*codebook));
    codebook->abi_version = GRID81_CODEBOOK_ABI_VERSION;

    /* Fixed mapping: lane value == column for CORE..BRIDGE, METRIC/NEUTRAL share col 8 */
    const uint32_t lane_to_col[] = {
        0, /* LANE_CORE(0) -> col 0 */
        1, /* LANE_DEFINITION(1) -> col 1 */
        2, /* LANE_SUPPORT(2) -> col 2 */
        3, /* LANE_CONTRADICTION(3) -> col 3 */
        4, /* LANE_QUALIFIER(4) -> col 4 */
        5, /* LANE_SCOPE(5) -> col 5 */
        6, /* LANE_CONTEXT(6) -> col 6 */
        7, /* LANE_BRIDGE(7) -> col 7 */
        8, /* LANE_METRIC(8) -> col 8 */
        8, /* LANE_NEUTRAL(9) -> col 8 */
    };
    for (uint32_t i = 0; i < GRID81_CODEBOOK_LANE_COUNT; i++) {
        codebook->entries[i].lane = i;
        codebook->entries[i].column = lane_to_col[i];
        memset(codebook->entries[i].reserved, 0, sizeof(codebook->entries[i].reserved));
    }
    codebook->entry_count = GRID81_CODEBOOK_LANE_COUNT;
    codebook->support_contradiction_distinct = 1;
    codebook->qualifier_scope_distinct = 1;
    codebook->bridge_context_distinct = 1;
    codebook->lane_does_not_determine_digit = 1;
    codebook->column_does_not_encode_semantic = 1;
}

int elpis_grid81_codebook_lookup(
    const elpis_semantic_grid81_codebook_v1 *codebook,
    uint32_t lane,
    uint32_t *out_column) {
    if (!codebook || !out_column) return SEMANTIC_E_INVAL;
    if (lane >= GRID81_CODEBOOK_LANE_COUNT) return SEMANTIC_E_INVAL;
    for (uint32_t i = 0; i < codebook->entry_count; i++) {
        if (codebook->entries[i].lane == lane) {
            *out_column = codebook->entries[i].column;
            return SEMANTIC_OK;
        }
    }
    return SEMANTIC_E_INVAL;
}

int elpis_grid81_codebook_identity(
    const elpis_semantic_grid81_codebook_v1 *codebook, hacf_digest *out) {
    if (!codebook || !out) return SEMANTIC_E_INVAL;
    elpis_sha256_ctx ctx;
    elpis_sha256_init(&ctx);
    const char domain[] = "elpis.semantic.grid81_codebook.v1";
    elpis_sha256_update(&ctx, (const uint8_t *)domain, strlen(domain));
    elpis_sha256_update(&ctx, (const uint8_t *)domain, 4);
    uint32_t f;
    f = codebook->abi_version;    elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    for (uint32_t i = 0; i < codebook->entry_count; i++) {
        f = codebook->entries[i].lane;   elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
        f = codebook->entries[i].column; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    }
    f = codebook->support_contradiction_distinct; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = codebook->qualifier_scope_distinct;       elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = codebook->bridge_context_distinct;        elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = codebook->lane_does_not_determine_digit;  elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    f = codebook->column_does_not_encode_semantic; elpis_sha256_update(&ctx, (uint8_t *)&f, 4);
    elpis_sha256_final(&ctx, out->bytes);
    return SEMANTIC_OK;
}

int elpis_grid81_codebook_validate(
    const elpis_semantic_grid81_codebook_v1 *codebook) {
    if (!codebook) return SEMANTIC_E_INVAL;
    if (codebook->abi_version != GRID81_CODEBOOK_ABI_VERSION) return SEMANTIC_E_INVAL;
    if (codebook->entry_count != GRID81_CODEBOOK_LANE_COUNT) return SEMANTIC_E_INVAL;
    /* Verify separation guarantees */
    uint32_t sup_col = 0, con_col = 0, qual_col = 0, scope_col = 0, bridge_col = 0, ctx_col = 0;
    for (uint32_t i = 0; i < codebook->entry_count; i++) {
        if (codebook->entries[i].column >= 9u) return SEMANTIC_E_INVAL;
        switch (codebook->entries[i].lane) {
            case 2: sup_col = codebook->entries[i].column; break;
            case 3: con_col = codebook->entries[i].column; break;
            case 4: qual_col = codebook->entries[i].column; break;
            case 5: scope_col = codebook->entries[i].column; break;
            case 7: bridge_col = codebook->entries[i].column; break;
            case 6: ctx_col = codebook->entries[i].column; break;
        }
    }
    if (sup_col == con_col) return SEMANTIC_E_INVAL;
    if (qual_col == scope_col) return SEMANTIC_E_INVAL;
    if (bridge_col == ctx_col) return SEMANTIC_E_INVAL;
    if (!codebook->support_contradiction_distinct) return SEMANTIC_E_INVAL;
    if (!codebook->qualifier_scope_distinct) return SEMANTIC_E_INVAL;
    if (!codebook->bridge_context_distinct) return SEMANTIC_E_INVAL;
    if (!codebook->lane_does_not_determine_digit) return SEMANTIC_E_INVAL;
    if (!codebook->column_does_not_encode_semantic) return SEMANTIC_E_INVAL;
    for (size_t i = 0; i < sizeof(codebook->reserved); i++) {
        if (codebook->reserved[i] != 0) return SEMANTIC_E_INVAL;
    }
    return SEMANTIC_OK;
}

int elpis_write_grid81_codebook(const char *path,
    const elpis_semantic_grid81_codebook_v1 *codebook) {
    if (!path || !codebook) return SEMANTIC_E_INVAL;
    int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t w = write(fd, codebook, sizeof(*codebook));
    if ((size_t)w != sizeof(*codebook)) { close(fd); return SEMANTIC_E_IO; }
    fsync(fd); close(fd);
    return SEMANTIC_OK;
}

int elpis_read_grid81_codebook(const char *path,
    elpis_semantic_grid81_codebook_v1 *out) {
    if (!path || !out) return SEMANTIC_E_INVAL;
    int fd = open(path, O_RDONLY);
    if (fd < 0) return SEMANTIC_E_IO;
    ssize_t r = read(fd, out, sizeof(*out));
    close(fd);
    if ((size_t)r != sizeof(*out)) return SEMANTIC_E_IO;
    return SEMANTIC_OK;
}
