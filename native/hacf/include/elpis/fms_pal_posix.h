/* elpis/fms_pal_posix.h - CPU + durable-disk PAL. No device tier: this PAL
 * reports FMS_CAP_COLD only, so a context built on it is WARM+COLD and any HOT
 * request follows cfg.hot_absent_policy. */
#ifndef ELPIS_FMS_PAL_POSIX_H
#define ELPIS_FMS_PAL_POSIX_H

#include "elpis/fms_pal.h"

#ifdef __cplusplus
extern "C" {
#endif

/* cold_root is created if absent. Returns NULL on failure. Ownership passes to
 * fms_create(); if the context is never created, call pal->destroy(pal->self). */
fms_pal *fms_pal_posix_create(const char *cold_root);

/* Token accessors. The token layout is private to this PAL; these are the only
 * ways to read it. token_path is test-only and is never called by the core. */
int         fms_pal_posix_token_digest(const fms_cold_token *t, uint8_t out[32]);
uint64_t    fms_pal_posix_token_bytes(const fms_cold_token *t);
const char *fms_pal_posix_token_path(const fms_cold_token *t);

#ifdef __cplusplus
}
#endif
#endif
