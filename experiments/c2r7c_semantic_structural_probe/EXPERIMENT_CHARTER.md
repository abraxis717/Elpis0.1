# C2R7-C isolated semantic→structural refinement probe

Status: EXPERIMENT_ONLY

Architecture:
typed semantic component
→ semantic-to-structural Projector
→ initial Grid81 state + frozen/writable scope + topology sidecar
→ recurrent TRM refinement
→ independently checked structural coherence
→ resolved topology

Grid81 is structural state, not prose and not an ordinal ballot.

Required invariants:
- prose has zero Grid81 authority for structured requests;
- structurally equivalent tasks may converge to the same Grid81;
- semantic identity remains distinct in the sidecar;
- topology-relevant mutations must affect structural state/support;
- structural residual must not read a hidden final grid;
- NO_OP/random controls must fail or underperform on withheld-topology fixtures;
- frozen loci remain frozen;
- filled-but-incoherent grids must still fail;
- capacity overflow fails closed; never truncate.

Hard nonclaims:
- no learned atomizer competence;
- no hierarchical ECS composition yet;
- no runtime admission;
- no production projector qualification.
