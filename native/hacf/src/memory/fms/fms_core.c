/* fms_core.c - FMS v2 core. Platform-free: no syscalls, no libm, no file paths.
 *
 * Locking order (single level, no nesting of FMS locks):
 *   ctx->mu  ->  PAL entry points
 * The lock is dropped around slow PAL work (cold_put/cold_get, hot_upload/
 * hot_download). Safety comes from reserving the destination charge BEFORE the
 * lock is dropped and marking the object FMS_ST_MOVING: a moving object cannot
 * be selected as a victim, unregistered, or moved again.
 */
#include "elpis/fms.h"
#include "elpis/fms_pal.h"

#include <stdlib.h>
#include <string.h>
#include <pthread.h>

#define NS_PER_SEC 1000000000.0
#define HIST_BUCKETS 48

typedef struct lease_s {
    struct lease_s *next;
    fms_id   id;
    void    *ptr;
    void    *fence;
    uint64_t bound_ns;
    uint8_t  tier;
    uint8_t  active;
    uint8_t  completed;
    uint8_t  pinned;
    fms_status terminal_status;
} lease_t;

typedef struct {
    fms_id   id;
    uint32_t kind;
    uint8_t  live, tier, state, dirty, zero_copy, cold_valid;
    uint32_t pin_count, lease_count;
    float    pin_priority;
    uint64_t size;
    uint64_t born_ns, last_access_ns, moved_ns, access_count;
    uint64_t skip_until_ns;                 /* transient move failure backoff */
    uint64_t pending[FMS_NDOMAINS];         /* charge reserved but not yet committed */
    uint8_t  pending_tier, has_pending;
    void    *host_ptr;
    void    *dev_ptr;
    fms_cold_token *cold;
    uint64_t charge[FMS_NDOMAINS];
} slot_t;

struct fms_ctx {
    fms_config      cfg;
    fms_pal        *pal;
    fms_hot_profile hot;
    int             hot_live, cold_live, device_lost;
    slot_t         *slots;
    uint32_t        nslots, gen;
    uint64_t        tier_bytes[FMS_NTIERS];
    uint64_t        dom_bytes[FMS_NDOMAINS];
    double          tokens;
    uint64_t        last_pump_ns;
    lease_t        *leases;
    pthread_mutex_t mu;
    uint32_t        hist[HIST_BUCKETS];
    uint64_t        hist_n;
    fms_stats       st;
};

/* ---- small helpers -------------------------------------------------------- */

static void lock(fms_ctx *c)   { pthread_mutex_lock(&c->mu); }
static void unlock(fms_ctx *c) { pthread_mutex_unlock(&c->mu); }
static uint64_t now_of(fms_ctx *c) { return c->pal->now_ns(c->pal->self); }

static uint64_t bw(fms_ctx *c, int from, int to) {
    uint64_t b = c->pal->bandwidth ? c->pal->bandwidth(c->pal->self, from, to) : 0;
    return b ? b : (1ull << 30);
}

static void hist_add(fms_ctx *c, uint64_t ns) {
    int b = 0;
    while (b < HIST_BUCKETS - 1 && (ns >> (b + 1))) b++;
    c->hist[b]++; c->hist_n++;
}

static uint64_t hist_pct(const fms_ctx *c, double p) {
    if (!c->hist_n) return 0;
    uint64_t target = (uint64_t)((double)c->hist_n * p), acc = 0;
    for (int b = 0; b < HIST_BUCKETS; b++) {
        acc += c->hist[b];
        if (acc >= target && c->hist[b]) return 1ull << b;
    }
    return 0;
}

/* Physical charge of one placement. Zero-copy HOT charges RAM exactly once:
 * the device view aliases the host allocation and adds no bytes. */
static void charge_for(const fms_ctx *c, uint64_t size, int tier, int zero_copy,
                       uint64_t out[FMS_NDOMAINS]) {
    memset(out, 0, sizeof(uint64_t) * FMS_NDOMAINS);
    if (tier == FMS_HOT)       out[zero_copy ? (int)FMS_DOM_RAM : (int)c->hot.domain] = size;
    else if (tier == FMS_WARM) out[FMS_DOM_RAM] = size;
    else                       out[FMS_DOM_STORAGE] = size;
}

/* Charge including a retained cold replica: a promoted object that keeps its
 * verified replica still occupies storage and must keep paying for it. */
static void plan_charge(const fms_ctx *c, const slot_t *s, uint64_t size, int tier,
                        int zero_copy, uint64_t out[FMS_NDOMAINS]) {
    charge_for(c, size, tier, zero_copy, out);
    if (tier != FMS_COLD && s->cold) out[FMS_DOM_STORAGE] = size;
}

static void apply_charge(slot_t *s, const uint64_t add[FMS_NDOMAINS]) {
    for (int d = 0; d < FMS_NDOMAINS; d++) s->charge[d] = add[d];
}

static int dom_admits(const fms_ctx *c, const uint64_t add[FMS_NDOMAINS]) {
    for (int d = 0; d < FMS_NDOMAINS; d++) {
        uint64_t ceil_b = c->cfg.domain_ceiling[d];
        if (!ceil_b) continue;                       /* 0 = unbounded domain */
        if (c->dom_bytes[d] + add[d] > ceil_b) return 0;
    }
    return 1;
}

static slot_t *lookup(fms_ctx *c, fms_id id) {
    uint32_t i = (uint32_t)(id & 0xffffffffu);
    if (i >= c->nslots) return NULL;
    slot_t *s = &c->slots[i];
    return (s->live && s->id == id) ? s : NULL;
}

static int tier_available(const fms_ctx *c, int tier) {
    if (tier == FMS_HOT)  return c->hot_live;
    if (tier == FMS_COLD) return c->cold_live;
    return 1;
}

/* Returns the tier to use, or -1 when policy says reject. */
static int eff_tier(fms_ctx *c, int t) {
    if (t < FMS_HOT) t = FMS_HOT;
    if (t > FMS_COLD) t = FMS_COLD;
    if (t == FMS_HOT && !c->hot_live)
        return c->cfg.hot_absent_policy == FMS_REJECT ? -1 : FMS_WARM;
    if (t == FMS_COLD && !c->cold_live)
        return c->cfg.cold_absent_policy == FMS_REJECT ? -1 : FMS_WARM;
    return t;
}

/* ---- relevance ------------------------------------------------------------ */

static double evict_cost_ns(fms_ctx *c, const slot_t *s, uint64_t now) {
    double sz = (double)s->size, demote_ns, promote_ns, tau, age, p;

    if (s->tier == FMS_HOT && s->zero_copy)      demote_ns = 1000.0;   /* drop an alias */
    else if (s->tier == FMS_WARM && s->cold && s->cold_valid && !s->dirty) demote_ns = 1000.0;
    else demote_ns = sz * NS_PER_SEC / (double)bw(c, s->tier, s->tier + 1);
    promote_ns = sz * NS_PER_SEC / (double)bw(c, s->tier + 1, s->tier);

    age = (double)(now - s->last_access_ns);
    tau = (double)(now - s->born_ns) / (double)(s->access_count + 1);
    if (tau < 1.0e6)  tau = 1.0e6;
    if (tau > 6.0e10) tau = 6.0e10;
    p = tau / (tau + age);

    return (demote_ns + p * promote_ns) * (1.0 + 8.0 * (double)s->pin_priority);
}

static int demotable(const fms_ctx *c, const slot_t *s) {
    if (!s->live || s->pin_count || s->lease_count) return 0;
    if (s->state != FMS_ST_RESIDENT) return 0;
    if (s->tier >= FMS_COLD) return 0;
    if (s->tier + 1 == FMS_COLD && !c->cold_live) return 0;
    return 1;
}

/* Victim in one tier (tier pressure). */
static slot_t *victim_in_tier(fms_ctx *c, int tier, uint64_t now, int relax) {
    slot_t *best = NULL; double best_v = -1.0;
    for (uint32_t i = 0; i < c->nslots; i++) {
        slot_t *s = &c->slots[i];
        if ((int)s->tier != tier || !demotable(c, s)) continue;
        if (now < s->skip_until_ns) continue;
        if (!relax) {
            if (now - s->moved_ns < c->cfg.cooldown_ns) continue;
            if (now - s->moved_ns < c->cfg.min_residency_ns) continue;
        }
        double v = (double)s->size / evict_cost_ns(c, s, now);
        if (v > best_v) { best_v = v; best = s; }
    }
    return best;
}

/* Victim whose demotion actually reduces pressure on `dom`. On an integrated
 * GPU, demoting HOT->WARM does not free RAM; only WARM->COLD does. */
static slot_t *victim_for_domain(fms_ctx *c, int dom, uint64_t now, int relax) {
    slot_t *best = NULL; double best_v = -1.0;
    uint64_t after[FMS_NDOMAINS];
    for (uint32_t i = 0; i < c->nslots; i++) {
        slot_t *s = &c->slots[i];
        if (!demotable(c, s)) continue;
        if (now < s->skip_until_ns) continue;
        if (!relax) {
            if (now - s->moved_ns < c->cfg.cooldown_ns) continue;
            if (now - s->moved_ns < c->cfg.min_residency_ns) continue;
        }
        charge_for(c, s->size, s->tier + 1, 0, after);
        if (after[dom] >= s->charge[dom]) continue;      /* no relief from this hop */
        double v = (double)s->size / evict_cost_ns(c, s, now);
        if (v > best_v) { best_v = v; best = s; }
    }
    return best;
}

static fms_status hop_down(fms_ctx *c, slot_t *s, uint64_t now);

/* Free space until the logical tier budget and every physical domain ceiling
 * admit `add`. Called with the lock held; may drop it inside hop_down. */
static fms_status reserve(fms_ctx *c, int tier, uint64_t bytes,
                          const uint64_t add[FMS_NDOMAINS], uint64_t now) {
    if (c->cfg.tier_budget[tier] && bytes > c->cfg.tier_budget[tier]) return FMS_E_LIMIT;

    uint32_t attempts = 0, cap = c->nslots * 2 + 8;
    for (;;) {
        int tier_ok = !c->cfg.tier_budget[tier] ||
                      c->tier_bytes[tier] + bytes <= c->cfg.tier_budget[tier];
        int dom_ok = dom_admits(c, add);
        if (tier_ok && dom_ok) return FMS_OK;
        if (++attempts > cap) return FMS_E_LIMIT;

        slot_t *v = NULL;
        if (!tier_ok) {
            v = victim_in_tier(c, tier, now, 0);
            if (!v) v = victim_in_tier(c, tier, now, 1);
        } else {
            for (int d = 0; d < FMS_NDOMAINS && !v; d++) {
                if (!c->cfg.domain_ceiling[d]) continue;
                if (c->dom_bytes[d] + add[d] <= c->cfg.domain_ceiling[d]) continue;
                v = victim_for_domain(c, d, now, 0);
                if (!v) v = victim_for_domain(c, d, now, 1);
            }
        }
        if (!v) return FMS_E_LIMIT;
        fms_status r = hop_down(c, v, now);
        if (r != FMS_OK) {
            /* hop_down owns fatal state transitions. Capacity, allocation and
             * recoverable I/O pressure must leave an intact source resident. */
            if (v->state == FMS_ST_RESIDENT) {
                v->skip_until_ns = now + 1000000ull;
            }
            if (r == FMS_E_LIMIT) return r;
        }
    }
}

/* ---- mover ---------------------------------------------------------------- */

/* Make the reservation visible immediately: the destination tier and every
 * domain delta are charged before any lock is dropped, so a concurrent thread
 * cannot spend the same headroom. */
static void hold_reservation(fms_ctx *c, slot_t *s, int to, const uint64_t delta[FMS_NDOMAINS]) {
    for (int d = 0; d < FMS_NDOMAINS; d++) { s->pending[d] = delta[d]; c->dom_bytes[d] += delta[d]; }
    s->pending_tier = (uint8_t)to;
    s->has_pending = 1;
    c->tier_bytes[to] += s->size;
}

static void drop_reservation(fms_ctx *c, slot_t *s) {
    if (!s->has_pending) return;
    for (int d = 0; d < FMS_NDOMAINS; d++) { c->dom_bytes[d] -= s->pending[d]; s->pending[d] = 0; }
    c->tier_bytes[s->pending_tier] -= s->size;
    s->has_pending = 0;
}

static void commit_move(fms_ctx *c, slot_t *s, int to, const uint64_t add[FMS_NDOMAINS],
                        uint64_t now, uint64_t t0) {
    uint64_t final_charge[FMS_NDOMAINS];
    memcpy(final_charge, add, sizeof final_charge);
    /* s->cold may have been created during this hop. */
    if (to != FMS_COLD && s->cold) final_charge[FMS_DOM_STORAGE] = s->size;
    for (int d = 0; d < FMS_NDOMAINS; d++) {
        c->dom_bytes[d] -= s->charge[d];
        c->dom_bytes[d] -= s->pending[d];
        s->pending[d] = 0;
    }
    s->has_pending = 0;
    c->tier_bytes[s->tier] -= s->size;        /* source */
    c->tier_bytes[to] -= s->size;             /* reservation on the destination */
    apply_charge(s, final_charge);
    for (int d = 0; d < FMS_NDOMAINS; d++) c->dom_bytes[d] += s->charge[d];
    c->tier_bytes[to] += s->size;
    s->tier = (uint8_t)to;
    s->moved_ns = now;
    s->state = FMS_ST_RESIDENT;
    hist_add(c, now_of(c) - t0);
}

static fms_status hop_down(fms_ctx *c, slot_t *s, uint64_t now) {
    int from = s->tier, to = from + 1;
    if (to > FMS_COLD) return FMS_E_LIMIT;
    if (to == FMS_COLD && !c->cold_live) return FMS_E_UNSUPPORTED;

    uint64_t add[FMS_NDOMAINS], t0 = now_of(c);
    plan_charge(c, s, s->size, to, 0, add);

    /* Delta reservation: the object already holds its current charge. */
    uint64_t delta[FMS_NDOMAINS];
    for (int d = 0; d < FMS_NDOMAINS; d++)
        delta[d] = add[d] > s->charge[d] ? add[d] - s->charge[d] : 0;

    s->state = FMS_ST_MOVING;
    fms_status r = reserve(c, to, s->size, delta, now);
    if (r != FMS_OK) { s->state = FMS_ST_RESIDENT; return r; }
    hold_reservation(c, s, to, delta);

    c->st.inflight_ops++;
    if (from == FMS_HOT) {
        if (s->zero_copy) {                       /* device view is an alias: just drop it */
            c->pal->hot_free(c->pal->self, s->dev_ptr, s->size);
            s->dev_ptr = NULL; s->zero_copy = 0;
        } else {
            void *h = NULL;
            if (c->pal->ram_alloc(c->pal->self, s->size, &h) != 0) {
                c->st.inflight_ops--; drop_reservation(c, s); s->state = FMS_ST_RESIDENT;
                return FMS_E_NOMEM;
            }
            void *dev = s->dev_ptr;
            unlock(c);
            int rc = c->pal->hot_download(c->pal->self, h, dev, s->size);
            lock(c);
            if (rc != 0) {
                c->pal->ram_free(c->pal->self, h, s->size);
                c->st.inflight_ops--; drop_reservation(c, s); c->st.device_failures++;
                c->st.move_failures++; s->state = FMS_ST_FAILED;
                return FMS_E_DEVICE;
            }
            c->pal->hot_free(c->pal->self, dev, s->size);
            s->dev_ptr = NULL; s->host_ptr = h;
        }
    } else {                                       /* WARM -> COLD */
        if (!s->cold || !s->cold_valid || s->dirty) {
            void *src = s->host_ptr; uint64_t n = s->size;
            fms_cold_token *tok = NULL;
            unlock(c);
            int rc = c->pal->cold_put(c->pal->self, src, n, &tok);
            lock(c);
            if (rc != 0) {
                c->st.inflight_ops--; drop_reservation(c, s); c->st.move_failures++;
                s->state = FMS_ST_RESIDENT;
                return rc == FMS_PAL_ENOMEM ? FMS_E_NOMEM : FMS_E_IO;
            }
            if (s->cold) c->pal->cold_drop(c->pal->self, s->cold);
            s->cold = tok; s->cold_valid = 1; s->dirty = 0;
            c->st.cold_writes++;
        } else {
            c->st.cold_replica_reuse++;
        }
        c->pal->ram_free(c->pal->self, s->host_ptr, s->size);
        s->host_ptr = NULL;
    }
    c->st.inflight_ops--;
    commit_move(c, s, to, add, now, t0);
    c->st.demotions++; c->st.bytes_demoted += s->size;
    return FMS_OK;
}

static fms_status hop_up(fms_ctx *c, slot_t *s, uint64_t now) {
    int from = s->tier, to = from - 1;
    if (to < FMS_HOT) return FMS_E_LIMIT;
    if (to == FMS_HOT && !c->hot_live) return FMS_E_UNSUPPORTED;

    int zc = (to == FMS_HOT) ? c->hot.zero_copy : 0;
    uint64_t add[FMS_NDOMAINS], t0 = now_of(c);
    plan_charge(c, s, s->size, to, zc, add);

    uint64_t delta[FMS_NDOMAINS];
    for (int d = 0; d < FMS_NDOMAINS; d++) {
        uint64_t held = s->charge[d];
        /* A non-zero-copy WARM->HOT hop holds both copies at its peak. */
        if (to == FMS_HOT && !zc && d == FMS_DOM_RAM) held = 0;
        delta[d] = add[d] > held ? add[d] - held : 0;
    }
    if (c->hot.stage_bytes_max && to == FMS_HOT && !zc)
        delta[FMS_DOM_RAM] += c->hot.stage_bytes_max;

    s->state = FMS_ST_MOVING;
    fms_status r = reserve(c, to, s->size, delta, now);
    if (r != FMS_OK) { s->state = FMS_ST_RESIDENT; return r; }
    hold_reservation(c, s, to, delta);

    c->st.inflight_ops++;
    if (from == FMS_COLD) {
        void *h = NULL;
        if (c->pal->ram_alloc(c->pal->self, s->size, &h) != 0) {
            c->st.inflight_ops--; drop_reservation(c, s); s->state = FMS_ST_RESIDENT;
            return FMS_E_NOMEM;
        }
        const fms_cold_token *tok = s->cold; uint64_t n = s->size;
        unlock(c);
        int rc = tok ? c->pal->cold_get(c->pal->self, tok, h, n) : FMS_PAL_EIO;
        lock(c);
        if (rc != 0) {
            c->pal->ram_free(c->pal->self, h, s->size);
            c->st.inflight_ops--; drop_reservation(c, s); c->st.move_failures++;
            s->state = FMS_ST_FAILED;                       /* never soft-recover corruption */
            if (rc == FMS_PAL_EDIGEST || rc == FMS_PAL_ESIZE) {
                c->st.digest_failures++;
                return FMS_E_DIGEST;
            }
            return FMS_E_IO;
        }
        c->st.cold_reads++;
        s->host_ptr = h;                                    /* cold replica retained */
    } else {                                                /* WARM -> HOT */
        void *dev = NULL;
        int rc = c->pal->hot_alloc(c->pal->self, s->size, zc ? s->host_ptr : NULL, &dev);
        if (rc != 0) {
            c->st.inflight_ops--; drop_reservation(c, s); s->state = FMS_ST_RESIDENT;
            c->st.device_failures++; c->st.forced_cpu_fallbacks++;
            return rc == FMS_PAL_EDEVICE ? FMS_E_DEVICE : FMS_E_NOMEM;
        }
        if (zc) {
            s->dev_ptr = dev; s->zero_copy = 1;
            c->st.zero_copy_placements++;
        } else {
            void *src = s->host_ptr; uint64_t n = s->size;
            unlock(c);
            int urc = c->pal->hot_upload(c->pal->self, dev, src, n);
            lock(c);
            if (urc != 0) {
                c->pal->hot_free(c->pal->self, dev, s->size);
                c->st.inflight_ops--; drop_reservation(c, s); c->st.device_failures++;
                c->st.move_failures++; c->st.forced_cpu_fallbacks++;
                s->state = FMS_ST_RESIDENT;
                return FMS_E_DEVICE;
            }
            c->pal->ram_free(c->pal->self, s->host_ptr, s->size);
            s->host_ptr = NULL; s->dev_ptr = dev; s->zero_copy = 0;
        }
    }
    c->st.inflight_ops--;
    commit_move(c, s, to, add, now, t0);
    c->st.promotions++; c->st.bytes_promoted += s->size;
    return FMS_OK;
}

/* ---- lifecycle ------------------------------------------------------------ */

static int pal_complete(const fms_pal *p) {
    return p && p->now_ns && p->ram_alloc && p->ram_free && p->destroy;
}

fms_ctx *fms_create(const fms_config *cfg, fms_pal *pal) {
    if (!cfg || !pal_complete(pal) || pal->abi != FMS_ABI_VERSION) return NULL;
    if (!cfg->max_objects) return NULL;
    if (!cfg->tier_budget[FMS_WARM] || !cfg->domain_ceiling[FMS_DOM_RAM]) return NULL;
    if (!(cfg->low_wm > 0.0f && cfg->low_wm <= cfg->high_wm && cfg->high_wm <= 1.0f)) return NULL;

    fms_ctx *c = calloc(1, sizeof *c);
    if (!c) return NULL;
    c->slots = calloc(cfg->max_objects, sizeof *c->slots);
    if (!c->slots) { free(c); return NULL; }
    if (pthread_mutex_init(&c->mu, NULL) != 0) { free(c->slots); free(c); return NULL; }

    c->cfg = *cfg; c->pal = pal; c->nslots = cfg->max_objects;

    c->hot.domain = FMS_DOM_DEVICE;
    memcpy(c->hot.backend, "none", 5);
    if (pal->hot_profile && (pal->caps & FMS_CAP_DEVICE)) {
        fms_hot_profile hp;
        memset(&hp, 0, sizeof hp);
        if (pal->hot_profile(pal->self, &hp) == 0 && hp.available) c->hot = hp;
    }
    c->hot_live = (pal->caps & FMS_CAP_DEVICE) && c->hot.available && cfg->tier_budget[FMS_HOT] &&
                  pal->hot_alloc && pal->hot_free && pal->hot_upload && pal->hot_download;
    if (c->hot.zero_copy && !(pal->caps & FMS_CAP_ZERO_COPY)) c->hot.zero_copy = 0;
    if (c->hot.domain >= FMS_NDOMAINS) c->hot.domain = FMS_DOM_DEVICE;

    c->cold_live = (pal->caps & FMS_CAP_COLD) && cfg->tier_budget[FMS_COLD] &&
                   pal->cold_put && pal->cold_get && pal->cold_drop;

    c->last_pump_ns = now_of(c);
    return c;
}

void fms_destroy(fms_ctx *c) {
    if (!c) return;
    lock(c);
    for (lease_t *l = c->leases; l;) { lease_t *n = l->next; free(l); l = n; }
    c->leases = NULL;
    for (uint32_t i = 0; i < c->nslots; i++) {
        slot_t *s = &c->slots[i];
        if (!s->live) continue;
        if (s->dev_ptr)  c->pal->hot_free(c->pal->self, s->dev_ptr, s->size);
        if (s->host_ptr) c->pal->ram_free(c->pal->self, s->host_ptr, s->size);
        if (s->cold)     c->pal->cold_drop(c->pal->self, s->cold);
    }
    unlock(c);
    pthread_mutex_destroy(&c->mu);
    c->pal->destroy(c->pal->self);
    free(c->slots);
    free(c);
}

fms_status fms_register(fms_ctx *c, uint32_t kind, uint64_t bytes, int want_tier,
                        float pin_priority, const void *init, fms_id *out) {
    if (!c || !out || !bytes) return FMS_E_INVAL;
    lock(c);
    int want = eff_tier(c, want_tier);
    if (want < 0) { unlock(c); return FMS_E_UNSUPPORTED; }

    uint32_t idx = c->nslots;
    for (uint32_t i = 0; i < c->nslots; i++) if (!c->slots[i].live) { idx = i; break; }
    if (idx == c->nslots) { unlock(c); return FMS_E_LIMIT; }

    uint64_t now = now_of(c), add[FMS_NDOMAINS];
    charge_for(c, bytes, FMS_WARM, 0, add);            /* everything is staged through WARM */
    fms_status r = reserve(c, FMS_WARM, bytes, add, now);
    if (r != FMS_OK) { unlock(c); return r; }

    void *h = NULL;
    if (c->pal->ram_alloc(c->pal->self, bytes, &h) != 0) { unlock(c); return FMS_E_NOMEM; }
    if (init) memcpy(h, init, (size_t)bytes); else memset(h, 0, (size_t)bytes);

    slot_t *s = &c->slots[idx];
    memset(s, 0, sizeof *s);
    s->id = ((uint64_t)(++c->gen) << 32) | idx;
    s->kind = kind; s->live = 1; s->tier = FMS_WARM; s->state = FMS_ST_RESIDENT;
    s->pin_priority = pin_priority; s->size = bytes; s->host_ptr = h;
    s->born_ns = s->last_access_ns = s->moved_ns = now;
    apply_charge(s, add);
    for (int d = 0; d < FMS_NDOMAINS; d++) c->dom_bytes[d] += s->charge[d];
    c->tier_bytes[FMS_WARM] += bytes;
    c->st.objects++;
    *out = s->id;

    if (want == FMS_HOT) { if (hop_up(c, s, now) != FMS_OK) c->st.forced_placements++; }
    else if (want == FMS_COLD) { if (hop_down(c, s, now) != FMS_OK) c->st.forced_placements++; }
    int tier = s->tier;
    unlock(c);
    return (fms_status)tier;
}

fms_status fms_unregister(fms_ctx *c, fms_id id) {
    if (!c) return FMS_E_INVAL;
    lock(c);
    slot_t *s = lookup(c, id);
    if (!s) { unlock(c); return FMS_E_NOTFOUND; }
    if (s->pin_count || s->lease_count || s->state == FMS_ST_MOVING) { unlock(c); return FMS_E_BUSY; }
    if (s->dev_ptr)  c->pal->hot_free(c->pal->self, s->dev_ptr, s->size);
    if (s->host_ptr) c->pal->ram_free(c->pal->self, s->host_ptr, s->size);
    if (s->cold)     c->pal->cold_drop(c->pal->self, s->cold);
    for (int d = 0; d < FMS_NDOMAINS; d++) c->dom_bytes[d] -= s->charge[d];
    c->tier_bytes[s->tier] -= s->size;
    s->live = 0; c->st.objects--;
    unlock(c);
    return FMS_OK;
}

/* ---- access --------------------------------------------------------------- */

/* Caller holds the lock. Pins first so the target can never be its own victim. */
static fms_status pin_at(fms_ctx *c, slot_t *s, int want, unsigned mode, void **ptr, int *tier_out) {
    if (s->state == FMS_ST_FAILED || s->state == FMS_ST_LOST) return FMS_E_STATE;
    if (s->state == FMS_ST_MOVING) return FMS_E_BUSY;

    uint64_t now = now_of(c);
    s->pin_count++;
    while ((int)s->tier > want) {
        fms_status r = hop_up(c, s, now);
        /* Corruption is fatal and never soft-recovered. A device transport
         * failure is not corruption: the CPU copy is still authoritative, so
         * the object stays where it is and the caller is told which tier it
         * actually got. hop_up() has already counted the fallback. */
        if (r == FMS_E_DIGEST) { s->pin_count--; return r; }
        if (r != FMS_OK) { if (r != FMS_E_DEVICE) c->st.forced_placements++; break; }
    }
    s->last_access_ns = now; s->access_count++;
    if (mode & FMS_WRITE) { s->dirty = 1; s->cold_valid = 0; }

    void *p = (s->tier == FMS_HOT && !s->zero_copy) ? s->dev_ptr
            : (s->tier == FMS_HOT) ? s->dev_ptr : s->host_ptr;
    if (!p) { s->pin_count--; return FMS_E_LIMIT; }
    *ptr = p; *tier_out = s->tier;
    return FMS_OK;
}

fms_status fms_acquire(fms_ctx *c, fms_id id, int want_tier, unsigned mode, void **ptr) {
    if (!c || !ptr || !(mode & (FMS_READ | FMS_WRITE))) return FMS_E_INVAL;
    lock(c);
    int want = eff_tier(c, want_tier);
    if (want < 0) { unlock(c); return FMS_E_UNSUPPORTED; }
    slot_t *s = lookup(c, id);
    if (!s) { unlock(c); return FMS_E_NOTFOUND; }
    int tier = 0;
    fms_status r = pin_at(c, s, want, mode, ptr, &tier);
    if (r == FMS_OK) c->st.pinned_bytes += s->size;
    unlock(c);
    return r == FMS_OK ? (fms_status)tier : r;
}

fms_status fms_release(fms_ctx *c, fms_id id) {
    if (!c) return FMS_E_INVAL;
    lock(c);
    slot_t *s = lookup(c, id);
    if (!s) { unlock(c); return FMS_E_NOTFOUND; }
    if (!s->pin_count) { unlock(c); return FMS_E_STATE; }
    s->pin_count--; c->st.pinned_bytes -= s->size;
    s->last_access_ns = now_of(c);
    unlock(c);
    return FMS_OK;
}

/* ---- leases and fences ---------------------------------------------------- */

fms_status fms_lease_acquire(fms_ctx *c, fms_id id, int want_tier, unsigned mode, fms_lease **out) {
    if (!c || !out || !(mode & (FMS_READ | FMS_WRITE))) return FMS_E_INVAL;
    lock(c);
    int want = eff_tier(c, want_tier);
    if (want < 0) { unlock(c); return FMS_E_UNSUPPORTED; }
    slot_t *s = lookup(c, id);
    if (!s) { unlock(c); return FMS_E_NOTFOUND; }
    void *p = NULL; int tier = 0;
    fms_status r = pin_at(c, s, want, mode, &p, &tier);
    if (r != FMS_OK) { unlock(c); return r; }

    lease_t *l = calloc(1, sizeof *l);
    if (!l) { s->pin_count--; unlock(c); return FMS_E_NOMEM; }
    l->id = id;
    l->ptr = p;
    l->tier = (uint8_t)tier;
    l->active = 1;
    l->pinned = 1;
    l->terminal_status = FMS_OK;
    l->next = c->leases;
    c->leases = l;
    s->lease_count++; c->st.pinned_bytes += s->size;
    unlock(c);
    *out = (fms_lease *)l;
    return FMS_OK;
}

void *fms_lease_ptr(const fms_lease *l) { return l ? ((const lease_t *)l)->ptr : NULL; }
int   fms_lease_tier(const fms_lease *l) { return l ? ((const lease_t *)l)->tier : -1; }

static lease_t *lease_find(fms_ctx *c, const fms_lease *handle) {
    for (lease_t *l = c->leases; l; l = l->next) {
        if ((const fms_lease *)l == handle) return l;
    }
    return NULL;
}

fms_status fms_lease_bind_fence(fms_ctx *c, fms_lease *lh, void *fence) {
    if (!c || !lh) return FMS_E_INVAL;
    lock(c);
    lease_t *l = lease_find(c, lh);
    if (!l) { unlock(c); return FMS_E_NOTFOUND; }
    if (!l->active || l->completed) { unlock(c); return FMS_E_STATE; }
    l->fence = fence;
    l->bound_ns = now_of(c);
    unlock(c);
    return FMS_OK;
}

/* Caller holds the lock. Drop the object pin exactly once, but retain the
 * caller-visible lease handle until explicit release. */
static void lease_finish(fms_ctx *c, lease_t *l, fms_status terminal) {
    if (!l || l->completed) return;
    slot_t *s = lookup(c, l->id);
    if (s && l->pinned) {
        if (s->lease_count) s->lease_count--;
        if (c->st.pinned_bytes >= s->size) c->st.pinned_bytes -= s->size;
        if (s->pin_count) s->pin_count--;
        s->last_access_ns = now_of(c);
    }
    l->pinned = 0;
    l->completed = 1;
    l->terminal_status = terminal;
    l->ptr = NULL;
}

/* Caller holds the lock. The handle must already be complete/unpinned. */
static void lease_unlink(fms_ctx *c, lease_t *l) {
    lease_t **pp = &c->leases;
    while (*pp && *pp != l) pp = &(*pp)->next;
    if (*pp) *pp = l->next;
    l->active = 0;
    free(l);
}

/* Caller holds the lock. Device loss: the buffer may still be written by a dead
 * context, so it is quarantined rather than reused. */
static void device_lost(fms_ctx *c, slot_t *s) {
    c->device_lost = 1;
    c->hot_live = 0;
    c->st.device_failures++;
    c->st.forced_cpu_fallbacks++;
    if (s) s->state = FMS_ST_LOST;
}

fms_status fms_lease_release(fms_ctx *c, fms_lease *lh) {
    if (!c || !lh) return FMS_E_INVAL;
    lock(c);
    lease_t *l = lease_find(c, lh);
    if (!l) { unlock(c); return FMS_E_NOTFOUND; }
    if (!l->active) { unlock(c); return FMS_E_STATE; }

    if (!l->completed && l->fence && c->pal->fence_query) {
        int fs = c->pal->fence_query(c->pal->self, l->fence);
        if (fs == FMS_FENCE_PENDING) { unlock(c); return FMS_E_BUSY; }
        if (fs == FMS_FENCE_LOST) {
            device_lost(c, lookup(c, l->id));
            lease_finish(c, l, FMS_E_DEVICE);
        } else {
            lease_finish(c, l, FMS_OK);
        }
    } else if (!l->completed) {
        lease_finish(c, l, FMS_OK);
    }

    fms_status result = l->terminal_status;
    lease_unlink(c, l);
    unlock(c);
    return result;
}

fms_status fms_reap(fms_ctx *c) {
    if (!c) return FMS_E_INVAL;
    lock(c);
    uint64_t now = now_of(c);
    fms_status worst = FMS_OK;
    for (lease_t *l = c->leases; l; l = l->next) {
        if (l->completed || !l->fence || !c->pal->fence_query) continue;
        int fs = c->pal->fence_query(c->pal->self, l->fence);
        if (fs == FMS_FENCE_COMPLETE) {
            lease_finish(c, l, FMS_OK);
        } else if (fs == FMS_FENCE_LOST) {
            device_lost(c, lookup(c, l->id));
            lease_finish(c, l, FMS_E_DEVICE);
            worst = FMS_E_DEVICE;
        } else if (c->cfg.fence_timeout_ns && now - l->bound_ns > c->cfg.fence_timeout_ns) {
            c->st.fence_timeouts++;
            device_lost(c, lookup(c, l->id));
            lease_finish(c, l, FMS_E_TIMEOUT);
            worst = FMS_E_TIMEOUT;
        }
    }
    unlock(c);
    return worst;
}

/* ---- control loop --------------------------------------------------------- */

fms_status fms_touch(fms_ctx *c, fms_id id) {
    if (!c) return FMS_E_INVAL;
    lock(c);
    slot_t *s = lookup(c, id);
    if (!s) { unlock(c); return FMS_E_NOTFOUND; }
    s->last_access_ns = now_of(c); s->access_count++;
    unlock(c);
    return FMS_OK;
}

fms_status fms_pump(fms_ctx *c) {
    if (!c) return FMS_E_INVAL;
    fms_reap(c);
    lock(c);
    uint64_t now = now_of(c), dt = now - c->last_pump_ns;
    c->last_pump_ns = now;

    if (c->cfg.move_rate_bps) {
        c->tokens += (double)c->cfg.move_rate_bps * (double)dt / NS_PER_SEC;
        if (c->tokens > (double)c->cfg.move_rate_bps) c->tokens = (double)c->cfg.move_rate_bps;
    }

    for (int t = FMS_HOT; t <= FMS_WARM; t++) {
        uint64_t budget = c->cfg.tier_budget[t];
        if (!budget || !tier_available(c, t)) continue;
        if ((double)c->tier_bytes[t] <= (double)budget * c->cfg.high_wm) continue;
        uint64_t floor_b = (uint64_t)((double)budget * c->cfg.low_wm);
        uint32_t attempts = 0;
        while (c->tier_bytes[t] > floor_b && attempts++ < c->nslots) {
            slot_t *v = victim_in_tier(c, t, now, 0);
            if (!v) break;
            if (c->cfg.move_rate_bps && c->tokens < (double)v->size) break;
            uint64_t sz = v->size;
            fms_status move = hop_down(c, v, now);
            if (move != FMS_OK) {
                if (v->state == FMS_ST_RESIDENT) {
                    v->skip_until_ns = now + 1000000ull;
                }
                if (move == FMS_E_LIMIT || move == FMS_E_NOMEM || move == FMS_E_IO) break;
                continue;
            }
            if (c->cfg.move_rate_bps) c->tokens -= (double)sz;
        }
    }

    /* Domain ceilings are enforced independently of logical tier watermarks. */
    for (int d = 0; d < FMS_NDOMAINS; d++) {
        uint64_t ceil_b = c->cfg.domain_ceiling[d];
        if (!ceil_b) continue;
        uint64_t floor_b = (uint64_t)((double)ceil_b * c->cfg.low_wm);
        uint32_t attempts = 0;
        while (c->dom_bytes[d] > (uint64_t)((double)ceil_b * c->cfg.high_wm) &&
               attempts++ < c->nslots) {
            slot_t *v = victim_for_domain(c, d, now, 0);
            if (!v) break;
            if (hop_down(c, v, now) != FMS_OK) break;
            if (c->dom_bytes[d] <= floor_b) break;
        }
    }
    unlock(c);
    return FMS_OK;
}

/* ---- introspection -------------------------------------------------------- */

fms_status fms_query(fms_ctx *c, fms_id id, fms_object_info *o) {
    if (!c || !o) return FMS_E_INVAL;
    lock(c);
    slot_t *s = lookup(c, id);
    if (!s) { unlock(c); return FMS_E_NOTFOUND; }
    memset(o, 0, sizeof *o);
    o->id = s->id; o->kind = s->kind; o->tier = s->tier; o->state = s->state;
    o->zero_copy = s->zero_copy; o->cold_replica = (uint8_t)(s->cold && s->cold_valid);
    o->pin_count = s->pin_count; o->lease_count = s->lease_count;
    o->size_bytes = s->size; o->last_access_ns = s->last_access_ns;
    o->access_count = s->access_count; o->pin_priority = s->pin_priority;
    for (int d = 0; d < FMS_NDOMAINS; d++) o->charge[d] = s->charge[d];
    o->ptr = (s->tier == FMS_HOT) ? s->dev_ptr : s->host_ptr;
    unlock(c);
    return FMS_OK;
}

void fms_get_stats(fms_ctx *c, fms_stats *out) {
    if (!c || !out) return;
    lock(c);
    *out = c->st;
    for (int t = 0; t < FMS_NTIERS; t++) out->tier_bytes[t] = c->tier_bytes[t];
    for (int d = 0; d < FMS_NDOMAINS; d++) out->domain_bytes[d] = c->dom_bytes[d];
    out->move_p50_ns = hist_pct(c, 0.50);
    out->move_p95_ns = hist_pct(c, 0.95);
    unlock(c);
}

int fms_hot_available(fms_ctx *c) {
    if (!c) return 0;
    lock(c);
    int v = c->hot_live;
    unlock(c);
    return v;
}

const char *fms_backend_name(fms_ctx *c) { return c ? c->hot.backend : "none"; }

const char *fms_strerror(int s) {
    switch (s) {
    case FMS_OK: return "ok";
    case FMS_E_INVAL: return "invalid argument";
    case FMS_E_NOMEM: return "allocator refused";
    case FMS_E_NOTFOUND: return "no such object";
    case FMS_E_BUSY: return "busy (pinned or fence pending)";
    case FMS_E_UNSUPPORTED: return "tier unavailable under policy";
    case FMS_E_IO: return "cold io failure";
    case FMS_E_LIMIT: return "no headroom";
    case FMS_E_STATE: return "bad object state";
    case FMS_E_DIGEST: return "cold digest mismatch";
    case FMS_E_DEVICE: return "device failure";
    case FMS_E_TIMEOUT: return "fence timeout";
    default: return s > 0 ? "ok (tier)" : "unknown";
    }
}
