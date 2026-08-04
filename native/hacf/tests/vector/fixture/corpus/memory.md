# Memory accounting

A tier is a latency class. A domain is a physical resource that can be
exhausted. On an integrated GPU both HOT and WARM charge system RAM.

## Residency

Vector shards are registered as FMS objects and leased at WARM for the
duration of scoring. HOT is never requested by the dense retrieval layer.
