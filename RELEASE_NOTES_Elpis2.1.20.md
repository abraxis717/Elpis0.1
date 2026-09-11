# Elpis2.1.20

## Version: v2.1.20

Elpis2.1.20 is the hosted-CI checkout-authority corrective successor to the
failed, untagged Elpis2.1.19 candidate.

Elpis2.1.19 remains immutable sealed evidence at
`43ecc65cceb910ccea232d463e4b8f24ace3545e`. It is not tagged, published,
resealed, force-rewritten, or added to `PUBLISHED_RELEASES.json`.

## Hosted CI correction

The Elpis2.1.19 hosted run demonstrated that the release object itself,
reference runtime, platform matrix, component attribution, public release
verifier, release/authority negative branches, native suites, runtime suites,
and previously repaired release seams are healthy.

The remaining repository-completeness failure was caused by its checkout
configuration, not by Elpis source semantics. That job used the default
`actions/checkout@v4` shallow checkout (`fetch-depth: 1`, no tags) and then ran
two tests that intentionally query Git authority:

- successor-component qualification commits must be ancestors of `HEAD`;
- `PUBLISHED_RELEASES.json` must match semantic `Elpis*` tags.

With a depth-1, tagless checkout, the historical qualification commit objects
and semantic tags are absent by construction. Elpis2.1.20 changes only that
job's checkout to fetch complete history and tags.

No runtime, native, Grid81, canonical, packaging-admission, or scientific
semantics are changed.

## Publication history

Elpis2.1.17, Elpis2.1.18, and Elpis2.1.19 are failed untagged candidates and
remain absent from the tag-derived publication registry. The registry remains
unchanged during this pre-seal phase.

## Explicit nonclaims

This corrective release does not authorize E1 or E2, establish learned-
refinement efficacy, execute Darwinian evolution, perform new scientific
evaluation, claim evolutionary benefit, autonomous self-improvement, general
RSI safety, hostile same-process isolation, process-external attestation,
generated-source execution authority, AGI, ASI, or full Elpis alignment.
