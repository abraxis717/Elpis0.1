# Grid81 Structural Semantics R1.1 — Component-Local Test Plan

## Scope ruling

This closure tests the existing deterministic symbolic-semantics component only. The package defines canonical Grid81 actions and pair payloads, the D4 action on 9×9 coordinates, orbit identity, quarantine identity, a structural-symbol registry, and passive projection/evidence contracts. It does not implement numerical embeddings, NumPy/PyTorch tensors, model inference, canonical Grid81 state access, or runtime actuation.

The three registered consumers declare `Grid81_Structural_Semantics` as a component dependency but do not directly import `elpis_grid81_semantics`. Their observed compatibility boundary is therefore:

1. shared Grid81/D4 geometry;
2. shared canonical compact JSON for compatible ASCII structural payloads;
3. manifest-level dependency declaration;
4. simultaneous importability with the R1.1 semantics package first on `PYTHONPATH`.

The typed and structural-group consumers enumerate the two axial reflections in the order vertical-midline then horizontal-midline, whereas the semantics enum names them by mirror axis in the reverse slot order. Compatibility is tested by geometric action and an explicit slot mapping, not by unqualified ordinal equality.

## Requirements matrix

| Requirement ID | Observed contract | Evidence source | Public symbol | Positive test | Negative test | Determinism relevance | Consumer compatibility relevance |
|---|---|---|---|---|---|---|---|
| G81SEM-API-001 | Root package exposes the exact declared `__all__` ABI. | `src/elpis_grid81_semantics/__init__.py`; `audit/API_SURFACE.json` | root exports | `test_declared_root_exports_are_exact_and_ordered`; `test_every_declared_export_resolves` | N/A | Stable import surface | Consumers and later packages can resolve the promoted boundary. |
| G81SEM-API-002 | Root exports resolve to enum, class, or function categories from this package. | `__init__.py`; package source | all root exports | `test_export_categories_match_contract`; `test_exports_originate_from_promoted_package_boundary` | `test_no_private_name_is_declared_as_root_abi` | Avoids environment-dependent shadow imports | Confirms R1.1 package wins import resolution. |
| G81SEM-API-003 | Public submodule helpers and schema constants remain available. | `actions.py`, `canonical.py`, `d4.py`, `quarantine.py`, `registry_contracts.py`, `projection_contracts.py` | helper functions/constants | `test_public_submodule_helpers_and_constants_are_available` | N/A | Constants bind canonical output | Consumers reproduce compatible geometry/serialization. |
| G81SEM-INV-001 | NOOP has null targets; EDIT has cell 0..80 and value 0..9. | `actions.py` | `Grid81ActionV1`, `ActionKindV1` | action round-trip, boundary, and factory tests | all explicit action validation branches | Canonical action bytes must be repeatable | Serialized action shape is a shared boundary. |
| G81SEM-INV-002 | Action JSON is compact, sorted, and round-trippable; `action` is an accepted input alias. | `actions.py` | `to_dict`, `from_dict`, `to_json` | `test_action_noop_round_trip_is_canonical`; alias test | invalid/missing kind tests | Exact bytes tested | Compatible with dictionary-based consumers. |
| G81SEM-INV-003 | Pair payload requires 81 grid values in 0..9, 81 binary mask values, and writable EDIT target. | `pairs.py` | `D4PairPayloadV1` | pair round-trip and schema-default tests | cardinality, domain, missing field, and nonwritable-target tests | Stable structural input domain | Matches typed consumer corpus field geometry. |
| G81SEM-INV-004 | Corpus rows map absent expansion to NOOP and rationale codes to values 0 or 6. | `pairs.py`; typed consumer corpus usage in `audit/CONSUMER_USAGE.json` | `from_corpus_row` | corpus-row mapping tests | nonwritable expansion test | Mapping is repeated exactly | Uses `input_grid`, `input_mask`, `expansion_targets`, `rationale_codes` observed downstream. |
| G81SEM-INV-005 | D4 contains exactly eight named elements in frozen semantics order. | `d4.py` | `D4`, `D4_ELEMENTS` | order/cardinality test | unknown element rejection | Enumeration drives orbit member order | Consumer reflection order is mapped explicitly rather than conflated. |
| G81SEM-INV-006 | Every D4 transform is a bijection and follows the frozen coordinate rules. | `d4.py` | transform functions | coordinate, index, grid, mask tests | unknown transform test | Permutations are exact integer operations | Compared as permutation sets to typed/group consumers. |
| G81SEM-INV-007 | D4 composition means apply right then left; inverses are two-sided. | `d4.py` | `compose`, `inverse`, table builders | exhaustive composition/inverse/table tests | N/A | Table construction must be stable | Establishes shared group geometry. |
| G81SEM-INV-008 | NOOP is invariant; EDIT moves only target cell; pair transform emits exact semantic fields. | `d4.py` | `transform_action`, `transform_pair` | action and pair transform tests | malformed actions are rejected at action construction | Exact transformed payloads feed canonicalization | Serialized payload crosses consumer canonicalizers. |
| G81SEM-INV-009 | Orbit compiler emits eight members, deduplicates identities, and satisfies orbit-size × stabilizer-size = 8. | `orbit.py` | `compute_orbit`, orbit dataclasses | symmetric/asymmetric orbit tests | N/A | Canonical representative and digest are repeated | D4-invariant structural identity underlies downstream orbit logic. |
| G81SEM-INV-010 | Pair-orbit digest binds schema ID/version, registry digest, and canonical representative bytes. | `canonical.py`, `orbit.py` | `pair_orbit_digest`, `compute_orbit` | helper/compiler equality and identity-sensitivity tests | N/A | Strong exact-byte identity | Prevents accidental cross-schema identity reuse. |
| G81SEM-INV-011 | Quarantine identity keeps canonical payload, raw bytes, and provenance as separate SHA-256 values. | `quarantine.py` | quarantine helpers | three-part identity tests | N/A | Each component is independently deterministic | Adjudicator consumes `canonical_payload_digest` fields. |
| G81SEM-INV-012 | Default registry binds symbols 0..9, required groups, and deterministic digest. | `registry_contracts.py` | registry class/factory | registry content and digest tests | missing void/opcode tests | Set-valued groups serialize in sorted form | Registry ID is the structural regime boundary. |
| G81SEM-INV-013 | Projection and selection-evidence records are passive; selection status is `EVIDENCE_ONLY`; sets serialize sorted. | `projection_contracts.py` | projection/evidence classes, audit helper | passive contract and sorted serialization tests | non-evidence status test | Sorted sets remove hash-seed dependence | Matches no-activation/no-authority consumer boundary. |
| G81SEM-INV-014 | Frozen dataclasses reject field rebinding, without claiming deep immutability of nested containers. | dataclass declarations | public dataclasses | frozen rebinding test | FrozenInstanceError | Stable record envelope | Avoids inventing a stronger consumer type contract. |
| G81SEM-NEG-001 | Every explicit public-input validation branch fails closed with its implemented exception type. | `actions.py`, `pairs.py`, `registry_contracts.py`, `projection_contracts.py`, `d4.py` | validating constructors/functions | N/A | `test_negative_cases.py` | Invalid inputs cannot enter deterministic identity | Protects downstream serialized assumptions. |
| G81SEM-MUT-001 | Canonicalization, transformation, orbit, pair conversion, quarantine, and passive audits do not mutate caller-owned inputs. | all public operation sources | public functions accepting structures | `test_input_nonmutation.py` | N/A | Mutation would contaminate repeated outputs | Consumers pass mutable dictionaries/lists. |
| G81SEM-MUT-002 | Projection/registry `to_dict` preserve specific observed nested aliases; this is documented rather than silently treated as deep-copy behavior. | `projection_contracts.py`, `registry_contracts.py` | `to_dict` | explicit alias-shape tests | N/A | Avoids false determinism assumptions after caller mutation | Prevents imposing an unsupported deep-immutability ABI. |
| G81SEM-DET-001 | Canonical bytes/digest ignore dictionary insertion order and match SHA-256 exactly. | `canonical.py` | `canonical_bytes`, `canonical_digest` | canonical order/digest tests | N/A | Core deterministic primitive | Compared against all three consumer canonicalizers. |
| G81SEM-DET-002 | Orbit, registry, quarantine, and evidence serialization repeat exactly in-process. | package source | relevant operations | `test_determinism.py` | identity-parameter sensitivity tests | Same-process gate | Shared identities remain stable. |
| G81SEM-DET-003 | Fixed public operations emit identical bytes across five fresh processes under random hash seeds. | `audit/fresh-process/probe.py`; handover | root API and factories | fresh-process probe | runner blocks on unequal hashes | Fresh-process gate | Confirms portability of serialized structural output. |
| G81SEM-COMPAT-001 | All three canonical manifests declare the semantics dependency and runtime admission remains false. | consumer `COMPONENT_MANIFEST.json`; `audit/CONSUMER_USAGE.json` | manifest boundary | manifest compatibility test | missing dependency fails | N/A | Direct registry-level compatibility claim. |
| G81SEM-COMPAT-002 | Three consumer packages import alongside R1.1 semantics, and semantics resolves to successor `src`. | consumer package boundaries | consumer package imports | import-resolution tests | wrong-path resolution fails | Prevents accidental old-root import | Confirms isolated successor precedence. |
| G81SEM-COMPAT-003 | Typed and group consumers implement the same eight D4 geometric actions, with explicit 4↔5 reflection slot mapping. | typed `d4.py`; group `orbit.py`; consumer audit | D4 permutation boundaries | set-equivalence and mapping tests | positional mismatch fails | Exact integer geometry | Direct geometry compatibility. |
| G81SEM-COMPAT-004 | Compatible ASCII semantics payloads canonicalize to identical compact JSON bytes in semantics, typed, group, and adjudication packages. | four canonicalization implementations; consumer audit | canonical serializers | cross-boundary canonical-byte test | byte mismatch fails | Exact bytes | Immediate serialized compatibility boundary. |

## Explicit non-claims

This suite does not claim:

- a learned vector embedding;
- NumPy or PyTorch interoperability;
- deep immutability of nested dataclass fields;
- direct Python-class consumption by the three downstream packages;
- runtime admission, model loading, state mutation, capability issuance, or promotion readiness beyond this test closure.
