# Elpis2.1.19

## Version: v2.1.19

Elpis2.1.19 is the corrective successor to the failed sealed local
Elpis2.1.18 candidate. Elpis2.1.18 remains immutable sealed evidence and is
not tagged, published, resealed, force-rewritten, or added to
`PUBLISHED_RELEASES.json`.

## Corrective sealed-control copy semantics

Elpis2.1.18 corrected release-manifest authority itself: in real Git
checkouts, manifest membership is derived from the Git-tracked publication
tree, so clone-local ignored `.astra_tmp` residue cannot become release
authority while physical-tree safety scans remain active.

Its post-seal local qualification then exposed a test-helper mismatch.
`tests/test_seal_release_mutations.py::copy_repo()` removed `.git` but copied
arbitrary clone-local files. The resulting Git-less control copy therefore
contained `.astra_tmp/.../lock`, causing the verifier's intentional Git-less
physical-tree fallback to report that local file as undeclared.

Elpis2.1.19 makes that copy helper publication-faithful. It copies the current
working-tree bytes for `git ls-files` membership and, during post-seal
qualification, explicitly includes the active write-once manifest if that
manifest is newly created but not yet committed. It does not copy unrelated
untracked or ignored clone state.

This is a qualification-harness correction. Runtime semantics, canonical
Grid81 contents, the 16-component public registry, the 17-component canonical
assembly, and the non-admission/non-packaging of the three Grid81 successor
writer packages remain unchanged.

## Publication history

The failed untagged Elpis2.1.17 and Elpis2.1.18 candidates are not published
releases. `PUBLISHED_RELEASES.json` remains tag-derived and unchanged during
this pre-seal phase.

## Explicit nonclaims

This corrective release does not authorize E1 or E2, establish learned-
refinement efficacy, execute Darwinian evolution, perform new scientific
evaluation, claim evolutionary benefit, autonomous self-improvement, general
RSI safety, hostile same-process isolation, process-external attestation,
generated-source execution authority, AGI, ASI, or full Elpis alignment.
