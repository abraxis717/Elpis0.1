# R2 memory accounting and FMS lifecycle

## Residency contract

```
verified shard bytes
  -> fms_register(kind = ELPIS_FMS_KIND_VECTOR_SHARD, want_tier = FMS_WARM)
  -> per-shard gate           (one promoter per shard)
  -> fms_lease_acquire(FMS_WARM, FMS_READ)
  -> exact CPU scoring, shard pinned for the whole scan
  -> fms_lease_release        (RAII, on success and on every error path)
  -> shard is demotable again
```

`FMS_HOT` is never passed to any FMS entry point in the vector layer. Every test
context sets `hot_absent_policy = FMS_REJECT`, so a HOT request would fail
loudly rather than fold down to WARM: the prohibition is enforced by
configuration, not asserted in prose.

Bytes are verified *before* `fms_register`, never after. The FMS object is the
only resident copy; the index keeps headers and digests, not payloads. There is
no permanent heap cache.

## Ordering and locks

```
elpis_vector_index::mu   shared for search/inspect/verify/list, exclusive for admit/close
ShardEntry::gate         one per shard, taken inside mu
fms_ctx internal lock    taken inside both, by FMS itself
```

The order is always index, then shard gate, then FMS. Last-error state is
`thread_local`, errno-style; a shared error slot written under a shared lock was
a real data race that ThreadSanitizer caught during development.

## Transient versus terminal FMS statuses

Two statuses are retried, under a wall-clock bound of five seconds with 200 us
backoff:

- `FMS_E_BUSY` — the object is mid-move: another reader is promoting it or the
  background pump is demoting it.
- `FMS_E_LIMIT` — no headroom *right now* because concurrent readers hold pins
  on other shards; those pins are released when their scans end.

Everything else is returned immediately. `FMS_E_DIGEST` in particular is never
retried and never downgraded.

The bound is wall-clock rather than an attempt count on purpose: one transient
move costs a cold I/O round trip, and that is far slower under a sanitizer or on
the MacBook target than on a workstation. A fixed attempt count silently becomes
a different timeout on every host.

## Sizing rule

```
WARM ceiling  >  concurrent queries  x  largest shard
```

Each query holds at most one lease at a time, so the worst case pinned footprint
is `min(threads, shards) x shard_size`. Below that, readers serialise on the
retry path; far below it they fail with `ELPIS_VEC_E_RESIDENCY` whose detail
names this rule. A ceiling smaller than a single shard fails earlier and more
cheaply, at admission, inside `fms_register`.

For the MacBook target the intended configuration is a 300 MiB WARM vector
ceiling, which at 1600 bytes per record is roughly 196k resident vectors, or
about 49k with four concurrent queries against equally sized shards. Tests use
2-8 MiB so that pressure, demotion and promotion are exercised rather than
theorised.

## Error mapping

| condition | vector status | cause preserved |
|---|---|---|
| corrupt cold replica | `ELPIS_VEC_E_INTEGRITY` | `FMS_E_DIGEST` |
| shard fails its own digest | `ELPIS_VEC_E_INTEGRITY` | 0 |
| structural rejection | `ELPIS_VEC_E_FORMAT` | 0 |
| no headroom at admission | `ELPIS_VEC_E_RESIDENCY` | `FMS_E_LIMIT` |
| deadline exceeded waiting | `ELPIS_VEC_E_RESIDENCY` | `FMS_E_BUSY` |
| profile or corpus mismatch | `ELPIS_VEC_E_PROFILE` | 0 |
| duplicate chunk digest | `ELPIS_VEC_E_DUPLICATE` | 0 |

An integrity failure is never converted into no results, not found, memory
exhaustion or temporary unavailability. `elpis_vector_index_last_error()`
returns both the vector status and the underlying `fms_status`.
