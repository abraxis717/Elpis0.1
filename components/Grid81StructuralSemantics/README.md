# Grid81 Structural Semantics

`Grid81StructuralSemantics` is the qualified deterministic symbolic-semantics layer for the Grid81 family.

Its public component identity is `Grid81_Structural_Semantics`.

The current qualified component version recorded by `COMPONENT_MANIFEST.json` is **R1.1.1**. Its pipeline role is **Grid81 structural semantics (S04)**, its qualification disposition is **QUALIFIED**, and its component-level `runtime_admission` remains **false**.

This README describes the current public component surface. Frozen qualification identity and provenance remain defined by [`COMPONENT_MANIFEST.json`](COMPONENT_MANIFEST.json) and the evidence referenced there.

## Scope

The component provides deterministic structural semantics for Grid81. Its qualified surface includes:

- canonical Grid81 action records;
- Grid81 pair payloads;
- the D4 action on 9×9 coordinates;
- deterministic D4 composition and inverse structure;
- orbit construction and orbit identity;
- canonical compact JSON serialization and digesting;
- quarantine identity;
- the structural-symbol registry;
- passive projection contracts;
- passive selection-evidence contracts.

The public Python package is `src/elpis_grid81_semantics/`.

The component does **not** own model inference, learned embeddings, canonical Grid81 state mutation, capability issuance, or runtime actuation.

## Structural objects

### Actions

The component defines canonical Grid81 actions with two structural action kinds: `NOOP` and `EDIT`.

`NOOP` carries no edit target.

`EDIT` addresses a Grid81 cell in the bounded range `0..80` and carries a value in the bounded range `0..9`.

Actions serialize through deterministic compact JSON and round-trip through the public action contract.

### Pair payloads

A structural pair contains:

- an 81-value Grid81 payload;
- an 81-value binary mask;
- a canonical action;
- associated structural fields required by the pair contract.

Grid values are constrained to `0..9`. Mask entries are binary. An `EDIT` target must be writable under the supplied mask.

Corpus conversion maps absent expansion to `NOOP` and preserves the frozen structural field contract used by the qualified component.

## D4 geometry

Grid81 Structural Semantics implements the eight-element D4 symmetry action over the 9×9 Grid81 coordinate space.

The qualified contract establishes:

- exactly eight named D4 elements;
- deterministic coordinate and index transformations;
- bijective transformations;
- composition defined as applying the right element and then the left;
- two-sided inverses;
- deterministic transformation of grids, masks, actions, and pair payloads.

The semantics component and downstream structural consumers share the same geometric action. Where reflection enum ordering differs between components, compatibility is established by explicit geometric mapping rather than ordinal equality.

## Orbit identity

The orbit layer compiles D4-related structural states into deterministic orbit records.

Qualified properties include:

- eight generated D4 members before identity deduplication;
- deterministic identity deduplication;
- canonical representative selection;
- orbit-size × stabilizer-size = 8;
- deterministic pair-orbit identity.

The pair-orbit digest binds the structural regime, including schema identity, registry identity, and canonical representative bytes.

It is a structural identity, not semantic truth or execution authority.

## Canonicalization and deterministic identity

The component uses compact, sorted JSON as a deterministic structural serialization boundary.

Canonicalization is designed so that dictionary insertion order does not affect canonical bytes or SHA-256 identity.

The qualified tests cover repeated in-process output and fresh-process reproduction under varied Python hash seeds.

## Quarantine identity

Quarantine identity deliberately separates:

- canonical structural payload identity;
- raw-byte identity;
- provenance identity.

These are independently digested rather than silently collapsed into one identifier.

## Structural-symbol registry

The default registry binds the Grid81 symbol domain `0..9`, required symbol groups, and a deterministic registry digest.

Set-valued registry fields serialize deterministically.

The registry identity defines a structural regime boundary; it does not grant runtime or semantic authority.

## Projection and evidence contracts

Projection and selection-evidence records are passive structural records.

The qualified selection status is `EVIDENCE_ONLY`.

These contracts do not activate capabilities or authorize execution.

## Downstream compatibility

The qualified compatibility boundary covers registered downstream consumers through:

1. shared Grid81/D4 geometry;
2. compatible canonical compact JSON for supported ASCII structural payloads;
3. manifest-level dependency declaration;
4. simultaneous importability with the qualified semantics package;
5. explicit geometric mapping where enum slot ordering differs.

Dependency declaration does not imply runtime admission.

## Authority boundary

This component is deterministic structural semantics only.

It does **not** claim or provide:

- learned vector embeddings;
- NumPy or PyTorch tensor semantics;
- model inference;
- trusted natural-language interpretation;
- canonical Grid81 state access;
- canonical Grid81 state mutation;
- capability issuance;
- execution authority;
- runtime admission;
- deep immutability of all nested caller-owned structures.

Its component-level `runtime_admission` remains false.

## Public source

Principal modules include:

| Module | Responsibility |
|---|---|
| `actions.py` | Canonical Grid81 structural actions |
| `pairs.py` | Structural pair payloads and corpus conversion |
| `d4.py` | D4 geometry, composition, transforms, inverses |
| `orbit.py` | Orbit construction and structural orbit identity |
| `canonical.py` | Canonical bytes and deterministic digesting |
| `quarantine.py` | Canonical/raw/provenance quarantine identity |
| `registry_contracts.py` | Structural-symbol registry |
| `projection_contracts.py` | Passive projection and selection-evidence records |

## Verification

The detailed component-local qualification matrix is in [`TEST_PLAN.md`](TEST_PLAN.md).

The authoritative component metadata and qualification provenance are recorded in [`COMPONENT_MANIFEST.json`](COMPONENT_MANIFEST.json).

## Architectural position

Grid81 Structural Semantics owns a deterministic symbolic structural vocabulary and geometry.

It should be read as structural representation plus deterministic symmetry/identity plus passive structural evidence—not as semantic understanding, learned reasoning, canonical mutation authority, or runtime execution authority.
