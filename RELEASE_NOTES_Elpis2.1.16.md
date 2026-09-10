# Elpis2.1.16

## Version: v2.1.16

Elpis2.1.16 is the documentation and Python-distribution launch successor to
the published Elpis2.1.15 release. Elpis2.1.15 remains immutable tagged and
GitHub-Release history; this successor does not amend, reseal, force-rewrite,
or otherwise replace it.

## README Paper R1

This release carries the qualified README Paper R1 reconciliation. The top-level
README now describes the current public repository without collapsing
coexisting qualified surfaces into one implied runtime pipeline.

The rewrite distinguishes the canonical public component registry from
additional qualified ingress surfaces, historical R0/R1 integrations, the
FPRM reference-model path, and the separate ECS Structural Authority R0
contract. It documents APW R0 and ECS R0/E0R2 while preserving their authority
and non-execution boundaries, reconciles the current Grid81 component family,
and removes stale frontier statements for repairs that already shipped.

Repository coexistence remains distinct from runtime integration.

## Python distribution and PyPI launch

The Python distribution project remains `elpisai`. The console command remains
`elpis`, and qualified Python import-package names remain unchanged.

The package metadata binds the top-level Markdown README as the PEP 621 project
readme and publishes canonical project links for the repository, issue tracker,
and changelog. Built wheel metadata must therefore carry the README as a
Markdown long description and expose those project URLs.

Base dependencies remain NumPy and SciPy. Torch and model-oriented dependencies
remain behind the explicit `trm` extra.

Elpis2.1.16 is intended to be the first public PyPI publication of this
repository under the distribution name `elpisai`. The unrelated PyPI project
named `elpis` is not this repository.

PyPI upload remains a distinct irreversible publication gate after the exact
release commit, hosted main CI, annotated tag, GitHub Release, and release-event
CI are qualified. The upload gate will build wheel and sdist from the exact
tagged source, run package checks, publish `elpisai==2.1.16`, read the release
back from PyPI, install it in a clean environment, and verify the installed
distribution/import/CLI contract.

## Release integrity

The release machinery advances the immutable predecessor belt through published
Elpis2.1.15 and adds a ratified Elpis2.1.16 release identity without changing
the historical primitive/runtime closure identity.

The README Paper R1 release-declaration regression becomes VERSION-driven so a
successor version cannot silently retain a hard-coded prior release declaration.

The Elpis2.1.16 manifest remains write-once. It is created only after the
documentation/package-metadata candidate passes pre-seal qualification. The
sealed candidate must then pass the public verifier, mutation suite, canonical
assembly checks, PyPI distribution-build checks, clean installed-package
qualification, and the complete top-level test suite before release commit
authority is accepted.

## Explicit nonclaims

This release does not establish the unresolved E0R2 semantic primitive,
authorize E1 or E2, establish learned-refinement efficacy, execute Darwinian
evolution, perform new scientific evaluation, claim evolutionary benefit,
autonomous self-improvement, general RSI safety, hostile same-process
isolation, process-external attestation, generated-source execution authority,
AGI, ASI, or full Elpis alignment.
