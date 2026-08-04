/* elpis/fms_pal_test.h - test-only PAL.
 *
 * Device emulation exists ONLY here and ONLY when emulate_device is set
 * explicitly. Production PALs (posix, accel) never fake a device. */
#ifndef ELPIS_FMS_PAL_TEST_H
#define ELPIS_FMS_PAL_TEST_H

#include "elpis/fms_pal.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct fms_pal_test_opts {
    const char *cold_root;
    int      emulate_device;    /* 0 => WARM+COLD only */
    int      device_domain;     /* FMS_DOM_RAM = integrated/shared, FMS_DOM_DEVICE = discrete */
    int      zero_copy;         /* device view aliases the host allocation */
    uint64_t stage_bytes_max;
    int      no_cold;           /* drop FMS_CAP_COLD: WARM-only configuration */
    /* fault injection */
    int      fail_hot_alloc, fail_hot_upload, fail_hot_download, fail_cold_put;
    int      fence_mode;        /* FMS_FENCE_COMPLETE | FMS_FENCE_PENDING | FMS_FENCE_LOST */
} fms_pal_test_opts;

fms_pal *fms_pal_test_create(const fms_pal_test_opts *o);
void fms_pal_test_set_fence_mode(fms_pal *p, int mode);
void fms_pal_test_set_faults(fms_pal *p, int alloc, int upload, int download);
uint64_t fms_pal_test_host_bytes(fms_pal *p);   /* live host bytes handed out by this PAL */
uint64_t fms_pal_test_device_bytes(fms_pal *p); /* live emulated-device bytes (0 when aliased) */

#ifdef __cplusplus
}
#endif
#endif
