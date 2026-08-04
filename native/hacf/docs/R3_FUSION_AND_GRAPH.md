# R3 Fusion and Graph Contract

## Policy

`elpis_hybrid_policy` fixes lexical and dense candidate limits, primary count,
graph seed count, neighbors per seed, total bundle count, RRF constant, source
weights and minimum graph-edge authority. Reserved fields must be zero. The
policy is serialized in fixed field order and hashed as `elpis.hybrid_policy.v1`.

The default is:

- lexical candidates: 32
- dense candidates: 32
- primary evidence: 12
- graph seeds: 4
- neighbors per seed: 2
- total bundle items: 20
- `rrf_k`: 60
- lexical/dense weights: 100/100

## Merge rules

Candidates merge exclusively by canonical chunk digest. A metadata disagreement
between lexical and dense results is an integrity failure. A chunk present in
both sources carries both rank fields and both source bits.

## Graph rules

Edges are sorted by subject, edge type, object digest, provenance digest and
authority. Neighbor pagination is over edges that satisfy minimum authority.
Namespace and corpus-authority filters are applied before evidence admission.
A graph edge to a chunk absent from the frozen corpus is a hard integrity error.
Already-selected chunks are skipped, and a graph-context item is never used as a
new seed in R3.
