# Elpis2.1.4 — Release-integrity successor

Elpis2.1.4 is a narrow mechanical successor to Elpis2.1.3. It does not change
runtime, Grid81, TRM, HACF, model, ABI, or authority semantics.

## Why this successor exists

After Elpis2.1.3 was sealed and published, `README.md` was rebuilt on `main`.
The README-only commit was legitimate documentation, but the release verifier
correctly rejected the new tree because the Elpis2.1.3 manifest still committed
the published README bytes.

Elpis2.1.3 is immutable, so this repair does **not** reseal or rewrite it.
Elpis2.1.4 binds the new README and the release-tooling repair into a new
successor manifest.

## Write-once sealing

`tools/seal_release.py` now treats manifest existence as the primary immutable
fact. If the selected release manifest already exists, sealing refuses unless
the explicit rewrite override is being used inside the verified throwaway
mutation-copy shape.

The historical `PUBLISHED` set remains a second independent belt and now
includes Elpis2.1.3.

This closes the design defect where a newly published release could remain
rewritable until somebody manually updated the `PUBLISHED` constant.

## Negative-branch qualification

The sealer now has direct negative tests for:

- refusal when the current release manifest already exists;
- refusal for a historically published version even when its manifest is
  removed in a throwaway test copy;
- refusal when ephemeral release artifacts are present;
- verification of the real sealed tree without a provisional reseal.

The historical sensitivity control is also preserved in qualification:
the unpatched `ab40edae373a3eb894f8557fa7d659c0b12acffa` sealer accepts
`--provisional` against the existing Elpis2.1.3 manifest and rewrites it.
That is the required pre-patch witness that the new negative branch was not
already enforced.

`tools/mutation_suite.py` still provisionally seals its own throwaway copy by
design. Its M0 therefore remains a mutation-harness control, not evidence that
the repository's real manifest is current. Real sealed-tree verification is a
separate no-reseal gate.

## Identity semantics

`primitive_closure_commit` remains
`482d4064321392108b87124cd47343d9c748f5bc` because this mechanical successor
does not move the qualified primitive/runtime closure.

`base_release_commit` remains
`c911af22e01ee35c441d65e8dbcad18694bdcb2a` because that field denotes the
existing distribution identity's original Elpis2.0.0 baseline, not the
immediate predecessor.

These values are deliberately retained, not derived by copying the previous
manifest.

## Immutability and scope

`manifests/Elpis2.1.2.RELEASE_MANIFEST.json` and
`manifests/Elpis2.1.3.RELEASE_MANIFEST.json` remain byte-for-byte unchanged.

Elpis2.1.3's capability-scope break, receipt verification semantics, runtime
dependency guards, scanner hardening, and other authority changes are inherited
unchanged.

No performance claim is made.
