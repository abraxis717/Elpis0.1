# Elpis2.1.17

## Version: v2.1.17

Elpis2.1.17 is the engineering-successor release to the published
Elpis2.1.16 line. Elpis2.1.16 remains immutable tagged and published history;
this successor does not amend, reseal, force-rewrite, or otherwise replace it.

## Grid81 canonical-writer engineering successor

This release carries the qualified post-2.1.16 Grid81 canonical-writer source
chain:

- deterministic canonical promotion authority;
- deterministic isolated canonical candidate construction;
- authority-gated atomic canonical publication;
- durable source-artifact replay exclusion;
- exact committed retry;
- production-reader post-publication verification;
- successor component manifests, dependency graph, and fail-closed assembly
  verifier.

The durable publication ledger uses the source structural artifact digest as
its uniqueness identity. The promotion-capability digest remains separately
authenticated by the publication receipt and candidate/canonical authority
chain. A fresh valid promotion capability therefore cannot republish a source
artifact that already has a durable publication reservation.

## Public and distribution boundary

The writer-chain source is qualified repository engineering, not a newly
admitted public runtime surface in this release.

The legacy public component registry remains the same 16-component assembly and
the canonical assembly remains the same 17-component assembly. The three
successor writer components retain `public_registry_admission=false` and
`runtime_admission=false`.

The top-level `elpisai` package-discovery contract also does not include:

- `elpis_grid81_promotion_authority`;
- `elpis_grid81_candidate_constructor`;
- `elpis_grid81_canonical_publisher`.

Accordingly, Elpis2.1.17 does not silently widen the installed Python package
surface merely because the qualified writer sources are present in the source
repository.

## Additional engineering hardening

The release also carries the post-2.1.16 durable Grid81 application-ledger and
runtime canonical-root authentication work, exhaustive ECS mutation-decoder
domain regression, Grid81 structural-semantics documentation reconciliation,
and writer-boundary documentation updates qualified on the successor line.

Repository coexistence remains distinct from runtime admission and from public
component-registry admission.

## Release integrity

The primitive/runtime closure identity remains unchanged from the ratified
baseline. Elpis2.1.17 receives its own write-once release manifest only after
this pre-seal candidate passes release-contract qualification.

`PUBLISHED_RELEASES.json` is not modified during pre-seal preparation. Its
declared source of truth is the actual `refs/tags/Elpis<semver>` set, so the
2.1.17 record can exist there only after publication authority exists.

## Explicit nonclaims

This release does not authorize E1 or E2, establish learned-refinement efficacy,
execute Darwinian evolution, perform new scientific evaluation, claim
evolutionary benefit, autonomous self-improvement, general RSI safety, hostile
same-process isolation, process-external attestation, generated-source
execution authority, AGI, ASI, or full Elpis alignment.

It also does not claim that repository-qualified canonical-writer components
are admitted into the public component registry, runtime assembly, or installed
`elpisai` distribution.
