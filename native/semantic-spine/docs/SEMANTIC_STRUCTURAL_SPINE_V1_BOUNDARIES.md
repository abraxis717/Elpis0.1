# Semantic Structural Spine V1 Boundaries

## Sealed Interior

The closed interior of Semantic Structural Spine V1 spans:

```
P5 bounded semantic view → P13 integrated structural-spine closure
```

P0-P4 provide qualified substrate and ingress dependencies but the closed replay
spine itself is P5-P13.

The sealed interior includes all qualified implementation, evidence, and test
artifacts produced during P0-P13. These artifacts are immutable.

## Inputs

Allowed inputs to the sealed spine:

- Qualified bounded semantic-view handoff (from P5)
- Qualified topology policy
- Qualified Grid81 compiler policy
- Qualified backend registry (from P12)
- Numeric board state
- Fixed and writable masks

## Outputs

Allowed outputs from the sealed spine:

- Structural packet
- Guarded structural state
- Bounded execution trace
- Structural observations
- Sidecar traceability
- Immutable receipts
- Closure manifests

## Authority Matrix

| Concern | Authority | Non-authoritative components |
|---------|-----------|------------------------------|
| Semantic identity | P5/P6 | All downstream components |
| Semantic relation | P5/P6 | All downstream components |
| Semantic provenance | P5/P6 | All downstream components |
| Semantic authority | P5/P6 | All downstream components |
| Topology | P6 | P7, P8, P9, backend |
| Grid81 placement | P7 | Backend, P8, P9 |
| Candidate proposal | DETERMINISTIC_MRV_SOLVER (proposal-only) | Backend has NO commit authority |
| Candidate decoding | P8 | Backend, P9 |
| State mutation | P8 (policy) + P9 (guard) | Backend cannot mutate directly |
| State commit | P9 (guard) | Backend cannot commit directly |
| Backend selection | P12 registry | P8, P9, backend |
| Traceability | Sidecar (observational) | Sidecar is NOT semantic authority |
| Runtime admission | No current component — FALSE | No spine component claims admission |

## Allowed Downstream Uses

Downstream programs may:

- Read the closure manifest.
- Bind the sealed spine as a dependency.
- Submit valid qualified inputs.
- Consume structural observations.
- Verify receipts and digests.
- Wrap the spine in a separate runtime transaction.
- Create a new explicitly versioned spine version (V2+).

## Prohibited Uses

Downstream programs may NOT:

- Modify sealed P0-P13 evidence.
- Reactivate ACTV1_Inner.
- Bypass P8/P9 guards.
- Treat MRV as semantic authority.
- Infer semantic meaning from digits.
- Alter backend selection silently.
- Redefine the P7 placement policy in place.
- Add fields to a sealed ABI without versioning.
- Call a runtime wrapper "qualified" based only on spine closure.
- Define `residual81` as though it were part of V1.
- Claim runtime admission is true.

## Versioning and Reopening Rules

Bugfixes that change canonical bytes, identities, behavior, policy, or
qualification evidence require a new version.

Semantic Structural Spine V1 remains immutable.

A replacement architecture must be named V2 or another explicit successor.

Historical negative results (P10, P10R) remain attached to V1.

## Runtime Boundary

The Semantic Structural Spine is a structural computation artifact. It does not
constitute a runtime service. Runtime admission remains FALSE.

The next program (Elpis Runtime Integration) is a separate effort that may wrap
this spine in a runtime transaction. Spine closure does not imply runtime
qualification. A runtime wrapper must prove its own properties independently.

Hermes may be mentioned only as external execution tooling when necessary.
Hermes is not part of the Semantic Structural Spine architecture. No Hermes
configuration belongs in these consolidation artifacts.
