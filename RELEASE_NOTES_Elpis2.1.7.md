# Elpis2.1.7 — README Paper R0

## Version: v2.1.7

Elpis2.1.7 is a documentation and release-identity successor to Elpis2.1.6.

Its purpose is to integrate the frozen README Paper R0 work into a new
successor release without modifying the already published Elpis2.1.6 release,
tag, manifest, or release object.

## README Paper R0

The repository root README is recast as a research-facing technical paper.

The new presentation is organized around:

- the Elpis research question and explicit scope;
- proposal without authority as the central architectural principle;
- semantic request representation;
- Grid81 structural projection;
- bounded learned structural guidance;
- authority and validation boundaries;
- validated-source runtime composition;
- qualified capabilities;
- known limitations and negative results;
- reproducibility and falsification;
- the public reference model;
- repository organization;
- the research frontier;
- release integrity and provenance.

The purpose is explanatory precision rather than marketing. Claims remain
bounded by shipped source, tests, frozen qualification evidence, and published
release authority.

The README Paper R0 source was independently frozen before release integration
at:

```text
commit:
1428de393d9b0c33360f5bc4c80c9f551e6b647a

README SHA-256:
0645fb79e90b92432f079d85efb05978aaaae8bdc2e6a2523787be7474481875
```

Release integration necessarily advances the README's canonical release
declaration and latest-release section from Elpis2.1.6 to Elpis2.1.7; the
research body is otherwise treated as the frozen documentation authority.

## Release-integrity succession

Elpis2.1.6 remains immutable.

Elpis2.1.7:

- receives its own `VERSION` identity;
- receives its own package-version identity;
- receives its own canonical and release-specific notes;
- receives its own write-once release manifest only after pre-seal
  qualification;
- advances the sealer's historical `PUBLISHED` belt through Elpis2.1.6;
- adds Elpis2.1.7 to the verifier's ratified release identities;
- extends the sealer guard tests so Elpis2.1.6 is explicitly covered as a
  published predecessor.

The primitive/runtime closure identity does not move because this release does
not alter the qualified primitive or runtime closure.

## Qualification boundary

The 2.1.7 release candidate is qualified through the existing fail-closed
release machinery, including:

- canonical declared-text binding against repository `VERSION`;
- the full 22-case intended-reason public-release mutation suite;
- write-once manifest guards;
- independent historical-published-version refusal;
- ephemeral-artifact and symlink-escape rejection;
- provisional sealing and verification in an isolated throwaway tree;
- post-seal verification of the exact real release tree before publication.

Qualification of this release establishes the integrity of the stated
documentation/release successor. It does not convert documentation into new
scientific or runtime evidence.

## Unchanged scientific and runtime boundaries

Elpis2.1.7 does **not**:

- repair the known C2R6-P0 allocation-completeness limitation identified by
  FuryanLocusOracle R0;
- alter Grid81 semantics;
- alter semantic request contracts;
- alter structural-guidance selection or transition semantics;
- alter learned-model authority;
- grant generated-source execution authority;
- alter receipt-verification semantics;
- alter CapabilityRegistry retention behavior;
- alter HACF behavior or ABI;
- alter model checkpoints;
- alter the Direct-E2E cross-process identity blocker;
- make a new performance claim.

Furyan remains a separately qualified finite placement oracle with deliberately
bounded claims. It is not promoted into implicit runtime authority by this
release.

The Python AST policy remains a static source-policy boundary. Passing it is not
a proof of arbitrary program correctness or a Python execution sandbox.

No performance claim is made.
