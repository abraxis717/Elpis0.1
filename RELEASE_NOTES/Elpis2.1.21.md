# Elpis2.1.21

## Version: v2.1.21

Elpis2.1.21 is the publication-authority corrective successor to the hosted-green,
untagged Elpis2.1.20 release candidate.

Elpis2.1.20 remains immutable sealed evidence at
`13444ef72e1aca98af4315d48e77144b8d72ebdf`. Its push workflows all passed,
but it is deliberately not tagged because the post-2.1.16 publication registry
introduced a circular authority dependency.

## Publication-registry correction

`PUBLISHED_RELEASES.json` is derived from `refs/tags/Elpis<semver>`. A new entry
requires both the final peeled tag commit and the release-manifest SHA. Those
facts do not exist until after sealing and tagging. Therefore the registry
cannot itself be part of the immutable pre-tag release-manifest file set.

Elpis2.1.21 makes the registry a post-tag projection:

- physical safety scanning still covers the registry;
- release-manifest membership excludes only `PUBLISHED_RELEASES.json`;
- ordinary branch CI requires exact registry/tag equality;
- tag-event CI permits exactly the current event tag to be pending;
- `tools/refresh_published_releases.py` deterministically materializes the exact
  tag-derived registry after tag qualification;
- the resulting registry-only post-publication commit does not mutate the
  sealed release payload.

No runtime, native, Grid81, canonical, package-admission, or scientific
semantics are changed.

## Explicit nonclaims

This corrective release does not authorize E1 or E2, establish learned-
refinement efficacy, execute Darwinian evolution, perform new scientific
evaluation, claim evolutionary benefit, autonomous self-improvement, general
RSI safety, hostile same-process isolation, process-external attestation,
generated-source execution authority, AGI, ASI, or full Elpis alignment.
