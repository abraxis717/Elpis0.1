# Elpis2.1.18

## Version: v2.1.18

Elpis2.1.18 is the corrective engineering successor to the failed, untagged
Elpis2.1.17 public-main candidate. Elpis2.1.17 remains immutable historical
evidence at commit `5fffb41446d2dd2011eb2d458bb61fbcc69a676a`; it is not tagged,
published, resealed, amended, force-rewritten, or added to the publication
registry.

## Corrective release-integrity work

The Elpis2.1.17 hosted qualification exposed three release-engineering defects:

- its write-once manifest accidentally bound clone-local ignored
  `.astra_tmp/.../lock` residue because sealing enumerated the physical checkout
  rather than the Git-tracked publication tree;
- the isolated runtime-guard mutation harness had not been updated when
  `_dependency_escape_audit()` gained authenticated canonical-root validation;
- the repository-only Grid81 canonical-writer chain test assumed repo-local
  non-shipped writer source roots were importable in the installed-artifact CI
  job.

Elpis2.1.18 repairs those three seams without changing runtime semantics.

Release manifest membership is now derived from `git ls-files` whenever Git
authority exists. Git-less throwaway mutation copies retain the historical
physical-tree fallback. Public secret/private-path and binary/artifact scans
remain physical-tree scans, so the change does not hide local safety residue;
it only prevents untracked clone state from becoming release authority.

The mutation harness now supplies an explicit synthetic identity validator for
its intentionally isolated canonical-root unit cases. Production R0/R1
canonical-root authentication remains unchanged and separately qualified.

The Grid81 writer-chain test now exposes the repository-only writer roots
explicitly for that source-tree test. The top-level `elpisai` package discovery
is unchanged: the promotion-authority, candidate-constructor, and canonical-
publisher packages remain non-shipped engineering source.

## Grid81 engineering boundary

The qualified post-2.1.16 Grid81 canonical-writer source chain remains present:
promotion authority, isolated candidate construction, authority-gated atomic
publication, durable source-artifact replay exclusion, exact committed retry,
production-reader verification, and successor assembly verification.

The published public component registry remains the 16-component assembly and
the canonical assembly remains the 17-component assembly. The three successor
writer components retain `public_registry_admission=false` and
`runtime_admission=false`.

## Publication history

`PUBLISHED_RELEASES.json` remains unchanged during 2.1.18 pre-seal work. It is
tag-derived publication history. The failed untagged 2.1.17 candidate is not
retroactively represented as a published release.

Elpis2.1.18 receives a new write-once release manifest only after corrective
pre-seal qualification succeeds. The Elpis2.1.17 manifest remains untouched.

## Explicit nonclaims

This corrective release does not authorize E1 or E2, establish learned-
refinement efficacy, execute Darwinian evolution, perform new scientific
evaluation, claim evolutionary benefit, autonomous self-improvement, general
RSI safety, hostile same-process isolation, process-external attestation,
generated-source execution authority, AGI, ASI, or full Elpis alignment.

It also does not admit the repository-qualified Grid81 writer components into
the public component registry, runtime assembly, or installed `elpisai`
distribution.
