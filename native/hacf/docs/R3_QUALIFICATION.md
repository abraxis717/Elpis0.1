# R3 Qualification

Construction qualification requires:

1. the sealed R2 baseline remains 15/15 green;
2. all R3 tests pass in Release mode;
3. ASan+UBSan pass with linked runtimes confirmed;
4. TSan passes, including concurrent hybrid retrieval;
5. the committed R3 fixture produces its expected policy, graph, query, bundle
   and HACF package identities;
6. source parity and fixture parity are reproduced on `elpis-mba72`;
7. only then may a formal R3 seal be created.

R3 adds six tests:

- `context_graph`
- `hybrid_fusion`
- `retrieval_bundle`
- `hybrid_adversarial`
- `hybrid_crosshost_fixture`
- `hybrid_concurrency`

The complete expected suite is 21 tests. The implementation manifest remains
`HACF_R3_IMPLEMENTED_NOT_SEALED` until authoritative host qualification and
cross-host parity are complete.
