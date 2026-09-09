# Elpis2.1.10

## Version: v2.1.10

Elpis2.1.10 is the qualified successor to Elpis2.1.9. It contains bounded
correctness, authority, packaging, CI-attribution, runtime, air-gap, and
claim-scope repairs described below.

The canonical release guard, mutation suite, write-once sealer, public
verifier, and sealed-tree controls qualify this candidate. Hosted workflow
status is recorded externally by GitHub Actions rather than asserted by this
static document; publication remains subject to the repository release policy.

Historical release authority remains immutable. Technical limitations and
explicitly unqualified surfaces remain stated below.

## Fixed invariant violations

- Native semantic-spine repairs digest overreads and self-referential/truncated
  TRM identities, validates bound semantic inputs, and registers all 96 root tests.
- Checkpoint loading hashes and deserializes the same bytes with restricted
  loading; typed admission preserves integrity failures and required observations.
- Joint allocation has an explicit finite node budget and typed exhaustion.
  AST filters reject audited implicit-capability bypasses, with grammar limits below.
- R1 uses one native wrapper authority and rejects over-limit/truncated data.
  Structural-guidance runtime requires caller-issued one-shot authorities;
  required-member defaults can no longer fabricate or suppress evidence.

## Security claim contractions

Grid81 does not claim durable publication or cross-process replay prevention.
CNumPyCortex Python hooks are defense-in-depth; network isolation rests on the
OS namespace witness. No repository-default inference endpoint remains.
Lineage/capability registries are process-local, not external attestation or
hostile same-process isolation. Planner audits report observed structured data,
not constant unobserved authority. P5 consumes a bound P2 report and supports
one graph hop. Repository status is explicitly historical descriptive prose.

## Schema and domain successors

- Native affected digest domains move to v2; TRM native-contract/policy/report/
  handoff and P5/P2 contracts have explicit successor identity. Native layout
  hashing remains non-portable; historical bytes are not reinterpreted.
- Inactive admission receipt, budget-bound projection ruleset/trace/result,
  planner data-check/observation, and caller-authority/runtime identities advance
  explicitly to v2 where documented. Valid observed admitted v1 payloads remain
  preserved; historical and successor golden fixtures are distinct.
- CNumPyCortex default channel schema moves from `cortex_default_v1`/1.0 to
  `cortex_default_v2`/2.0. Operators own endpoint configuration.
- Repository status moves to `elpis.repository-status.v2`, retaining old v1
  content under `historical_snapshot`; it grants no current qualification.

## CI and packaging

The root wheel ships `elpis`, `elpis_reference` and the narrow Darwinian
geometry/constants/projector surface. Torch remains optional through `elpis[trm]`;
Torch-free imports and explicit dependency failures are qualified independently.
TRM supports the root NumPy 1.26.4 environment. Component attribution covers
21 owners (17 new, four existing), with fail-fast disabled and external-suite
limits explicit. Native CI defines 96-test gates, Werror and sanitizer checks;
CNumPyCortex defines an independent OS witness. Hosted workflow results remain
external CI records rather than static claims in this document.

## Residual limitations and deliberately unimplemented work

P0.5 remains partial: async/generator grammar disposition is unresolved. P0.6
full external qualification lacks required phase evidence. The header release
boundary is undefined. Real checkpoint compatibility and learned efficacy remain
externally unqualified. No independent P2.3 semantic oracle was manufactured;
Grid81 leaves 13 of 36 descriptive relations unmet. Portable native digest
serialization and the fixture/set 62-character digest defect remain deferred.
No durable Grid81 writer, cross-process authority, new duplicate registry or
status freshness generator was added. The historical assembly verifier still
requires the deliberately unshipped Nanbeige host.


The limitations above define the public release boundary for this version.
