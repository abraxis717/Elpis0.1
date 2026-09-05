# Elpis2.1.1

Elpis2.1.1 is a correctness and persistence hardening successor to
Elpis2.1.0.

Qualified implementation authority before release sealing:

`4fb460005048b3d7ed6743b51529e833bc44a2f0`

## Graph persistence and identity

- Bound snapshot manifest segment counts.
- Make snapshot reads transactional and exact-length.
- Enforce snapshot genesis/tip chain continuity.
- Reject snapshot aggregate-counter overflow without mutation.
- Publish immutable segment files with atomic no-replace ownership.
- Validate snapshots before replacing published manifests.
- Size HACF operation allocation for provenance multiplicity.
- Verify complete persisted segment payloads, identities, references,
  exact length, and HACF digests before publishing reader outputs.
- Guard public semantic identity functions against invalid arguments and
  participant counts outside the admitted bound.

## Read-only view correctness

- Honor offset, limit, and output-capacity contracts across snapshot-view
  enumeration and traversal APIs.
- Replace injected snapshot-view records transactionally.
- Canonicalize stored record ordering so binary lookup and enumeration
  operate over the same ordering invariant.
- Enumerate actual referenced base nodes in embedding-composed views.
- Preserve output bounds and deterministic pagination.
- Make composed base/overlay enumeration agree with lookup precedence and
  duplicate-inclusive totals.

## Qualification

- Debug semantic-spine build: PASS.
- Compiler warnings in the qualified build: none.
- Focused ASan/UBSan graph and view qualification: PASS.
- Aggregate semantic-spine CTest: 94/96.
- The only two aggregate failures are the unchanged
  `embedding_boundary` and `context_boundaries` qualification tests,
  which retain obsolete path/environment assumptions. They are recorded
  as known mechanical qualification exclusions and are not counted as
  passing tests.
- Worktree was clean at qualified implementation authority.
- No performance improvement is claimed by this release.

## Compatibility and authority

- Public C ABI remains unchanged.
- Existing v1 persisted-format semantics remain unchanged.
- The v1 segment format continues to commit the HACF projection rather
  than every physical file byte.
- Registry definitions are not newly persisted by this release.
- `BASIC_REGEX_SHIPMENT_R1` and its bounded StreamingRegexIngress v1
  contract remain unchanged.
- Arbitrary-length Regex streaming is not claimed.
- No new model, validation, execution, or terminal-output authority is
  granted by this release.
