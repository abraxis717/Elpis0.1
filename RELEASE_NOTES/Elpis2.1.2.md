# Elpis2.1.2

Elpis2.1.2 is a mechanical CI qualification successor to Elpis2.1.1.

No production runtime, semantic-spine, ABI, persisted-format, model,
authority, or algorithmic behavior changes in this release.

## Reference-runtime CI repair

The Elpis2.1.1 reference-runtime workflow successfully built and installed
`elpis-2.1.1`, but its installed-package smoke test still asserted that the
installed package version must equal the literal string `2.1.0`.

Elpis2.1.2 removes that stale release-specific assertion.

The installed-package smoke test now reads the expected package version from
the repository `VERSION` authority and compares installed package metadata
against that value.

This makes the reference-runtime qualification release-independent while
continuing to verify that the installed artifact matches the checked-out
release identity.

## Elpis2.1.1 status

Elpis2.1.1 remains immutable at its published release commit.

Its CI failure was mechanical: the public release verifier passed, package
build and installation succeeded, the validated-source smoke passed, CI
passed, and platform-matrix passed. The failing assertion compared the
successfully installed 2.1.1 package against the obsolete literal `2.1.0`.

Elpis2.1.1 is not rewritten or retagged by this release.

## Compatibility and authority

- Public C ABI unchanged.
- v1 persisted-format semantics unchanged.
- Basic Regex R1 semantics unchanged.
- Runtime admission and authority boundaries unchanged.
- No new model authority.
- No validation or execution authority is granted.
- No performance claim.
