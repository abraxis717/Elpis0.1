# Grid81 Deterministic Canonical Promotion Authority

This component is the explicit authority bridge between the advisory G5.3E
canonical-promotion plan and the Grid81 atomic canonical publisher.

It does not write canonical state.

## Why this component exists

The G5.3E planner deliberately emits a non-executable, non-self-applying,
non-authoritative plan. A canonical writer must therefore not treat a READY
planning decision as write permission.

This component preserves that boundary. It requires an explicit external
operator-approval digest before it can issue a one-use
`ATOMIC_GRID81_CANONICAL_PROMOTION` capability.

## Inputs bound into the capability

The issued capability binds:

- the exact G5.3E promotion-plan digest;
- the exact promotion-decision digest;
- the complete G5.3B/C/D source-chain digest;
- the G5.3C structural artifact digest;
- the source structural-influence capability digest;
- the application-receipt digest;
- the resulting shadow-state digest;
- the source G5.3C application-ledger head;
- the separately expected canonical-publication ledger head;
- a deterministic reserved canonical transaction ID;
- the currently verified canonical Grid81 digest;
- the current generation semantic digest;
- the immediate successor generation number and path;
- the fixed R0 authority-policy digest;
- the explicit external operator-approval digest.

## Authority boundary

The capability grants only the bounded Grid81 promotion operations required by
the atomic publisher:

- append one immediate successor generation;
- create the corresponding canonical HEAD;
- do not overwrite an existing generation;
- do not overwrite an unrelated HEAD;
- do not write ECS world state.

It is one-use and starts in `GRANTED_UNCONSUMED`.

The capability object is data, not an executor.

## Operator approval

R0 requires an explicit 64-hex operator-approval digest.

That digest is a binding only. This component does **not** claim that a bare
digest authenticates a human, proves possession of a private key, or constitutes
a digital signature. Strong operator authentication can be added at a separate
boundary without changing the source-chain or target-generation semantics.

## Non-claims

This component does not:

- authenticate operator identity;
- mutate canonical Grid81 state;
- construct generation payloads;
- consume the capability;
- apply structural influence to ECS;
- turn the G5.3E planner itself into an authority source.
