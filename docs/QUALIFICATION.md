# Qualification Evidence

## Qualified dispositions

| Disposition | Status |
|------------|--------|
| ELPIS_RUNTIME_INTEGRATION_R0_DETERMINISTIC_TRANSACTION_QUALIFIED | QUALIFIED |
| ELPIS_RUNTIME_INTEGRATION_R1_BOUNDED_PREREFINEMENT_RETRIEVAL_QUALIFIED | QUALIFIED |
| ELPIS_RUNTIME_INTEGRATION_R1_CANONICAL_HYGIENE_RECONCILED | RECONCILED |
| ELPIS_RUNTIME_R0_R1_GRID81_R1_1_CANONICAL_REBIND_QUALIFIED | QUALIFIED |
| GRID81_STRUCTURAL_SEMANTICS_R1.1.1_PROMOTED | QUALIFIED |

## Test results

| Suite | Result |
|-------|--------|
| Grid81 R1.1.1 direct tests | 122/122 PASS |
| Grid81 consumer compatibility | 5/5 PASS |
| Grid81 fresh-process determinism | 9/9 PASS |
| Runtime R0 | 26/26 PASS |
| Runtime R0 negative cases | 13/13 PASS |
| Runtime R0 determinism | 5/5 PASS |
| Runtime R1 | 24/24 PASS |
| Runtime R1 negative cases | 12/12 PASS |
| Runtime R1 determinism | 5/5 PASS |

## HACF wrapper

- External HACF wrapper SHA-256: `94e887f19623b7339e4f0d3c51d82f1c83e09141ef994261ca92f317bd7affd0`
- Buildable from published source via CMake
- No RPATH/RUNPATH dependencies on local paths
- Dynamic dependencies are system libraries only

## Canonical non-mutation

- 0 canonical source mutations
- 0 runtime implementation mutations
- Grid81 HEAD unmodified
- Grid81 generation 000001 unmodified
- Darwinian canonical state unmodified
