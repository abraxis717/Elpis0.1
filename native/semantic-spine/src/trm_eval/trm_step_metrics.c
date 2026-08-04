/* trm_step_metrics.c — Per-step evaluation metrics. */
#include "elpis_semantic/trm_step_metrics.h"
#include <stdio.h>
#include <string.h>

void elpis_trm_step_metrics_init(elpis_semantic_trm_step_metrics_v1 *m) {
    memset(m, 0, sizeof(*m));
    m->abi_version = TRM_STEP_METRICS_VERSION;
}

int elpis_trm_step_metrics_validate(const elpis_semantic_trm_step_metrics_v1 *m) {
    if (m->abi_version != TRM_STEP_METRICS_VERSION) return -1;
    return 0;
}

int elpis_write_trm_step_metrics(const char *path,
    const elpis_semantic_trm_step_metrics_v1 *m) {
    FILE *f = fopen(path, "wb"); if (!f) return -1;
    size_t sz = sizeof(*m);
    if (fwrite(m, 1, sz, f) != sz) { fclose(f); return -1; }
    fclose(f); return 0;
}

int elpis_read_trm_step_metrics(const char *path,
    elpis_semantic_trm_step_metrics_v1 *out) {
    FILE *f = fopen(path, "rb"); if (!f) return -1;
    size_t sz = sizeof(*out);
    if (fread(out, 1, sz, f) != sz) { fclose(f); return -1; }
    fclose(f); return elpis_trm_step_metrics_validate(out);
}
