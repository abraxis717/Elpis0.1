# Elpis2.1.23

## Version: v2.1.23

Elpis2.1.23 is a repository-organization and ECS evidence-publication successor to the immutable Elpis2.1.22 release.

## ECS consolidation

The public ECS surface is consolidated under `ECS/`. The pre-existing Structural R0 authority and authority header move byte-for-byte to `ECS/ECS_AUTHORITY/STRUCTURAL_R0/` and `ECS/ECS_AUTHORITY_HEADER.md`. The executable ECS resolver and current tests follow the new paths; the frozen authority payload bytes and digest pins are unchanged.

## Branch35–40 scientific evidence

The closed Branch35–40 evidence handoff is imported byte-for-byte under `ECS/science/`. Its outer handoff authority and every nested `SHA256SUMS` authority are reverified before import.

Branch40 remains exactly:

- `PASS_BRANCH40_WEAK_S3_DYNAMICAL_RELEVANCE`
- `Outcome_A_RETAIN_FULL_ACTIVE_S3`
- 144 scientific worlds, width-stratified across N in {36, 48, 72}
- `R8_material_consumed = false`
- `branch41_material_generated = false`

The bounded scientific claim is that, under the frozen cubic d=6 Branch36 dynamics, matched weak-S3 interventions are future-dynamically distinguishable from S3-fiber microscopic controls across all tested widths under the frozen Branch40 primary trajectory criterion, while robust-S3 controls provide positive causal sensitivity. The weak S3 coordinates therefore carry latent future-dynamical state under the tested regime.

This does not establish global Markov sufficiency, an exact minimal state dimension, exact gauge symmetry or null directions, global dynamical equivalence, universal width independence, semantic meaning, memory, topology, reasoning, learning-theoretic optimality, generalization beyond the frozen regime, ECS runtime admission, Elpis architectural admission, autonomous self-improvement, evolutionary benefit, AGI, or ASI.

## Release-note archive

Historical release notes are consolidated under `RELEASE_NOTES/`, and the README again surfaces the current release notes immediately after its opening abstract. Historical note bytes are moved without rewriting their contents.

## Release-authority continuity

Elpis2.1.22's tag, manifest, GitHub Release, and publication-registry entry remain unchanged. Elpis2.1.23 receives its own successor manifest only after the migrated tree passes qualification.
