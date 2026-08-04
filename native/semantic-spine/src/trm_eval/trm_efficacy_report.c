/* trm_efficacy_report.c — Aggregate efficacy report. */
#include "elpis_semantic/trm_efficacy_report.h"
#include <stdio.h>
#include <string.h>
#include "elpis/sha256.h"

void elpis_trm_efficacy_report_init(elpis_semantic_trm_efficacy_report_v1 *r) {
    memset(r, 0, sizeof(*r));
    r->abi_version = TRM_EFFICACY_REPORT_VERSION;
}

int elpis_trm_efficacy_report_identity(
    const elpis_semantic_trm_efficacy_report_v1 *r, hacf_digest *out) {
    uint8_t hash[32];
    elpis_sha256((const void *)r, offsetof(elpis_semantic_trm_efficacy_report_v1, reserved), hash);
    memcpy(out->bytes, hash, sizeof(out->bytes));
    return 0;
}

int elpis_trm_efficacy_report_validate(const elpis_semantic_trm_efficacy_report_v1 *r) {
    if (r->abi_version != TRM_EFFICACY_REPORT_VERSION) return -1;
    if (r->model_efficacy_verdict > 3) return -1;
    return 0;
}

int elpis_write_trm_efficacy_report(const char *path,
    const elpis_semantic_trm_efficacy_report_v1 *r) {
    FILE *f = fopen(path, "wb"); if (!f) return -1;
    size_t sz = sizeof(*r);
    if (fwrite(r, 1, sz, f) != sz) { fclose(f); return -1; }
    fclose(f); return 0;
}

int elpis_read_trm_efficacy_report(const char *path,
    elpis_semantic_trm_efficacy_report_v1 *out) {
    FILE *f = fopen(path, "rb"); if (!f) return -1;
    size_t sz = sizeof(*out);
    if (fread(out, 1, sz, f) != sz) { fclose(f); return -1; }
    fclose(f); return elpis_trm_efficacy_report_validate(out);
}
