# P0 Protocol Contract

## Composition

\[
P_0(q,c)
=
V
\circ D
\circ C
\circ E
\circ T
\circ \Pi(q,c)
\]

Where:

- \(\Pi\) emits an immutable `StructuralProjection`.
- \(T\) emits a non-authoritative `TRMRefinementProposal`.
- \(E\) emits an `ExpertActivationProposal`.
- \(C\) intersects proposed experts with a static allow-list and
  creates a `DecoderControlPlan`.
- \(D\) emits an offline deterministic Python artifact.
- \(V\) emits validator evidence without executing the artifact.

## Ownership

```text
TRM proposes
controller executes
P0 shadow account records cost intents
validators assess
governance remains inactive
````

## Non-authority invariants

1. `expansion_executed == false`.
2. `executed_experts == ()`.
3. `governance_invoked == false`.
4. Every P0 accounting event has `shadow == true`.
5. The input and every stage output are immutable dataclasses.
6. Identical input produces an identical `result_digest`.
7. No generated Python artifact is executed.
8. No persistent memory is written.
9. No HRM output is authoritative.
10. No proposed expert is loaded into a decoder.

## P0 trace

```text
projection.produced
trm.proposal_only
experts.proposal_only
controller.compiled_static_plan
controller.expansion_deferred      # only when proposed
decoder.artifact_emitted
validator.AST_VALID | failure code
```

## Admission gates for P0.1

A real Grid81 TRM adapter may replace `ShadowTRMProposer` only if:

* it emits the exact `TRMRefinementProposal` contract;
* it performs no account transition;
* it performs no expansion;
* it performs no expert loading;
* it does not authorize STOP;
* fresh-process replay is deterministic for fixed weights and input;
* the controller remains the only executor.

The admitted L0 `RequestAccount` may later replace the P0 shadow account
through an adapter. P0 itself must not duplicate affine authority logic.
