# Elpis2.1.22

## Version: v2.1.22

Elpis2.1.22 is the structural-guidance authority-integrity successor to the
published and immutable Elpis2.1.21 release.

The successor carries the independently qualified D1+D2 repair from commit
`1195907c2f3ee19eabbde49a02aec7078399f2ee`.

## Structural-guidance authority reconciliation

`load_ruleset()` now resolves the source paths of the four imported production
authority modules, hashes the exact executing source bytes, and rejects any
frozen-digest mismatch before constructing a ruleset.

The live production authority identities are:

- `elpis_p0/structural_residual.py`:
  `d517be0041cf61dafe7813bd4b443982723288b43e7ab30f69c8075459c9b5ca`
- `c2r7c/structural_trm_features.py`:
  `d1dec9488c7eca67008b14b7e9d6fb620c48965f417f8a30c5486b5d5df427b2`
- `elpis_p0/contracts.py`:
  `8f0d7e14774d02ea068833bb4fa91eee43c14b1733371edac52a7cba019005a1`
- `elpis_p0/semantic_ir.py`:
  `d4c44e586c7869ff1ab8621e0f0ddd638784951f2583b847b75efc07f788f519`

The public structural-guidance authority declarations re-export the internal
pins, removing the stale duplicate structural-residual declaration.

The corrected P0 contract identity changes the deterministic ruleset,
projection, and trace identity digests that transitively bind that authority.
Allocator structural outputs, lane bindings, masks, residuals, semantic IDs,
and topology are unchanged.

## Release-authority continuity

Elpis2.1.21 remains immutable. Its tag, release manifest, publication registry,
published PyPI files, and GitHub Release are not rewritten or resealed by this
successor.

Elpis2.1.22 receives its own write-once release manifest and release identity.

## Explicit nonclaims

This successor does not authorize new execution surfaces, alter allocator
policy semantics, authorize E1 or E2, establish learned-refinement efficacy,
execute Darwinian evolution, claim autonomous self-improvement, general RSI
safety, AGI, ASI, or full Elpis alignment.
