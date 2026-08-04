# Darwinian Matrix — System Philosophy and Current Contract

## Status

**Experimental substrate under active construction.**

This document distinguishes:

1. what the Darwinian Matrix is intended to become;
2. what the current code actually implements;
3. what remains hypothetical or unqualified.

The presence of this package inside `Elpis_Canon` does not grant it runtime authority.

The package does not currently consume G5.2B capabilities, instantiate G5.3A consumption transactions, produce structural-influence artifacts, apply structural influence, select models or adapters, or activate any runtime component.

---

## I. The narrow claim

The intended architectural claim is:

> A persistent frozen Grid81 may be able to drive a persistent two-dimensional ecological substrate through spatially mapped, globally coordinated regional climate shifts.

That claim has not yet been tested with the production TRM.

The current code has established a smaller foundation:

> A deterministic 81-region climate field can parameterize a persistent 81×81 ecological substrate through immutable regional mapping, continuous climate response functions, gradient-conditioned diffusion, bounded ecological transactions, and deterministic frame assessment.

The current implementation proves substrate mechanics, not TRM usefulness.

---

## II. Current implementation boundary

The current package implements:

- exact solved and partial Grid81 validation;
- a contiguous 81×81 ecological lattice containing 6,561 sites;
- 81 regions containing exactly 81 sites each;
- deterministic flat-index geometry;
- diagnostic epicenter coordinates;
- reflective and toroidal outer-boundary tables;
- four-neighbor and eight-neighbor stencil support;
- detached climate-sidecar read views;
- immutable persistent climate-dynamics state;
- region-owned transition ages;
- directed climate-transition identities in the domain `0..80`;
- continuous climate optimum, capacity, and shock functions;
- structure-of-arrays ecological storage;
- double-buffered resource diffusion;
- gradient-conditioned edge permeability;
- deferred birth and death command infrastructure;
- producer, consumer, and structure component types;
- one bounded atomic ecological transaction;
- deterministic state and telemetry digests;
- an enforced deterministic Torch runtime policy;
- chained canonical ecological frame records;
- exact single-frame ecological replay;
- six-way frame classification;
- immutable meta-episode attempt accounting;
- a pre-TRM climate-arrangement probe;
- tests and three-seed determinism probes for the implemented substrate.

The current package does **not** implement:

- a production frozen-TRM adapter;
- persistent TRM hidden or recurrent state;
- projector constraint transactions;
- clamp assertion, replacement, or release;
- ecological feedback into the projector;
- error-derived clamps;
- user clarification behavior;
- operational gap detection;
- contradiction adjudication;
- a full tick controller;
- persisted full-episode state snapshots;
- autonomous reconstruction of a complete multi-frame episode from disk;
- automated reproduction or birth policy;
- component migration;
- mutation or lineage evolution;
- TRM cascade measurement;
- a qualified cascade prior;
- expert, model, or adapter routing;
- structural-influence consumption;
- runtime actuation.

Prototype files must not be described as operational merely because they exist.

---

## III. Geometry and ownership

The structural source domain is one Grid81:

\[
G_t \in \{1,\ldots,9\}^{9\times9}.
\]

The ecological domain is one contiguous:

\[
D_t \in \mathcal{S}^{81\times81}.
\]

It contains:

- 6,561 ecological sites;
- 81 climate regions;
- 81 sites per region;
- patch width 9;
- patch radius 4.

The region mapping is:

\[
\pi(y,x)
=
9\left\lfloor\frac{y}{9}\right\rfloor
+
\left\lfloor\frac{x}{9}\right\rfloor.
\]

Diagnostic epicenters are located at:

\[
\epsilon(i,j)=(9i+4,\;9j+4).
\]

These coordinates are visual and geometric reference points only.

Climate is **not** stored inside those lattice sites.

All 6,561 lattice positions remain ordinary ecological positions.

Climate exists in a separate sidecar:

```text
current_climate[81]
previous_climate[81]
transition_ids[81]
changed_mask[81]
transition_age[81]
````

The ecological engine receives detached region-level or lattice-expanded read views.

The ecological engine has no writable reference to the climate sidecar.

This is an implemented ownership guarantee, not merely a convention.

---

## IV. Exact Grid81 semantics

The current solved Grid81 domain is:

```text
digits 1..9
81 total values
each row contains 1..9 exactly once
each column contains 1..9 exactly once
each 3×3 box contains 1..9 exactly once
```

Partial grids use:

```text
0 = empty
1..9 = asserted value
```

Partial validity and solved validity are separate predicates.

A total sum of 405 is necessary for a solved `1..9` Sudoku but is not sufficient. Invalid grids can also sum to 405, and the code explicitly rejects them through row, column, and box validation.

---

## V. Fixed marginals and free arrangement

Every valid solved Grid81 contains each digit exactly nine times.

Therefore the following are fixed:

* digit histogram;
* global digit sum of 405;
* sums of scalar functions that depend only on digit multiplicity;
* the current climate optimum sum;
* the current climate capacity sum.

The TRM cannot alter those global marginals while remaining inside valid Sudoku structure.

It may only rearrange where the nine copies of each value occur.

That does **not** imply ecological viability is conserved.

The implemented arrangement probe compared eight valid Sudoku-preserving arrangements over the same heterogeneous ecological field.

Every arrangement retained:

```text
digit sum:       405
capacity sum:    59.0625000000
digit counts:    nine occurrences of every digit
```

Yet the measured spatial quantities varied:

```text
orthogonal total absolute gradient: 454 to 470
mean orthogonal permeability:       0.387027 to 0.405913
diagonal zero-gradient edges:       4 to 12
instantaneous suitability span:     61.65023738
```

The empirical conclusion is:

> Grid81 conserves the climate histogram but does not conserve interaction geometry or ecological opportunity.

The arrangement of fixed climate values changes:

* adjacency cost;
* diffusion permeability;
* alignment with spatially heterogeneous genomes;
* local suitability;
* corridor and barrier placement.

The TRM, once connected, cannot create or destroy climate mass. Its possible contribution is the rearrangement of interaction geometry.

Whether that rearrangement is useful remains an ablation question.

---

## VI. Orthogonal and diagonal structure

Orthogonally adjacent Grid81 regions share a row or column.

Their digits are therefore always distinct in a valid Sudoku.

Orthogonal climate gradients are guaranteed nonzero.

Diagonal adjacency has more nuanced constraints:

* diagonal neighbors within the same 3×3 box must be distinct;
* diagonal neighbors crossing box boundaries may repeat;
* the two long board diagonals are not independent Sudoku constraint groups.

Consequently, diagonal equal-climate edges may exist, but cheaper diagonal transport is not universally guaranteed.

It is a state-dependent measurable property.

The code must observe transport geometry rather than assume it.

---

## VII. Climate semantics

A Grid81 digit is a scalar parameter.

It is not inherently:

* truth;
* falsehood;
* repair;
* failure;
* dormancy;
* hostility;
* authority;
* expert identity;
* model identity;
* activation.

The current climate response defines continuous functions.

For a digit (g\in{1,\ldots,9}), the ecological optimum is:

[
\mu(g)=\frac{g-1}{8}.
]

The base carrying capacity is non-monotonic and peaks near digit five:

[
K(g)
====

k_{\min}
+
(k_{\max}-k_{\min})
\left(
1-
\left(\frac{|g-5|}{4}\right)^2
\right).
]

Directed climate transitions are encoded bijectively:

[
\tau(a,b)
=========

9(a-1)+(b-1),
]

with transition IDs in `0..80`.

A transition shock is directional:

[
\sigma(a,b,t)
=============

\frac{b-a}{8}e^{-t/\tau}.
]

Thus:

[
2\rightarrow7
\neq
7\rightarrow2.
]

The code contains no digit-specific semantic lookup table.

Ecological laws may depend continuously on digit value, climate mismatch, transition direction, transition age, and local gradient.

---

## VIII. Discrete occupancy and continuous fields

The current ecology is a hybrid substrate.

Occupancy is discrete:

```text
one site
one component type or empty
stable lineage integer
deferred structural mutation
```

Resource is continuous:

```text
float32[6561]
read buffer
write buffer
atomic swap
gradient-conditioned diffusion
```

The component types are:

```text
PRODUCER
CONSUMER
STRUCTURE
```

The current bounded transaction gives them distinct behavior:

### Producer

A producer:

* has a genome in `0..1`;
* is evaluated against the local climate optimum;
* generates resource according to suitability and effective capacity;
* converts part of production into energy;
* adapts its genome slowly toward the local optimum.

### Consumer

A consumer:

* has a genome in `0..1`;
* consumes locally available resource;
* has climate-conditioned demand;
* converts consumed resource into energy;
* adapts its genome slowly toward the local optimum.

### Structure

A structure component:

* is currently immobile;
* increases neighboring effective carrying capacity;
* pays a lower maintenance cost;
* reacts to directed climate shock;
* does not currently reproduce or migrate.

The current transaction automatically schedules deaths when energy falls below the configured threshold.

The command buffer supports deferred births, but no automated birth or reproduction law is currently active.

This distinction must remain explicit.

---

## IX. Field diffusion and borders

The global ecological plane is continuous across internal 9×9 patch borders.

Internal patch boundaries are not walls.

The currently tested default neighbor table is:

```text
outer boundary: reflective
stencil: Moore eight-neighbor
internal patch borders: contiguous
```

Alternative supported geometry includes a four-neighbor stencil and toroidal outer boundaries, but those are not the default ecological probe configuration.

Resource exchange across an edge is reduced continuously by climate difference:

[
\rho_{nm}
=========

e^{-\alpha |g_n-g_m|}.
]

Equal climates yield permeability one.

Large climate differences reduce permeability without creating an absolute barrier.

The diffusion implementation:

* reads only from the resource read buffer;
* writes only to the resource write buffer;
* performs an explicit atomic buffer swap;
* leaves the read buffer unchanged during the pass;
* remains deterministic under the tested seeds.

Components do not currently migrate.

Only the continuous resource field crosses site and region boundaries.

---

## X. Atomic ecological transaction

The implemented ecological transaction:

1. validates the input state;
2. validates detached climate telemetry;
3. validates transition ages and neighbor geometry;
4. clones the ecological state;
5. calculates climate-gradient permeability;
6. performs double-buffered resource diffusion;
7. calculates climate optimum, capacity, and directed shock;
8. applies producer, consumer, and structure behavior;
9. adapts eligible genomes;
10. increments active component ages;
11. stages and flushes deaths;
12. validates the resulting state;
13. proves that input state, climate, and transition ages were not mutated;
14. returns a new ecological state and deterministic telemetry.

On failure, no staged result is returned as a successful transaction.

This is the current atomicity boundary.

It is not yet part of a larger projector/TRM/controller transaction.

---

## XI. Frame assessment

The implemented controller layer currently classifies ecological viability trajectories using six verdicts:

```text
RESOLVED
IMPROVING
DEGRADING
STALLED
OSCILLATING
BUDGET_EXHAUSTED
```

`RESOLVED` and `BUDGET_EXHAUSTED` are terminal.

Resolution takes precedence when the target is reached on the final permitted attempt.

Each meta-episode currently tracks:

```text
meta_id
attempt_budget
attempt_index
viability_history
closed state
final terminal verdict
```

Assessments and meta states have deterministic canonical digests.

The current viability scalar is:

[
V_t
===

\sum_n
\mathbf{1}[\text{active}_n]
,
\max(E_n,0)
,
K_n.
]

This scalar is an implemented diagnostic, not a universal definition of task correctness.

It does not directly authorize clamps or structural changes.

---

## XII. Intended meta-task architecture

The intended future system uses a two-tier clock:

### Meta-episode

One user problem or query.

### Attempt frame

One bounded cycle:

```text
projector
→ constraint transaction
→ frozen TRM relaxation
→ cascade extraction
→ climate-sidecar update
→ bounded ecological transaction
→ frame assessment
→ ledger commit
```

That complete cycle is not implemented yet.

The future authority direction is intended to be:

[
D \rightarrow P \rightarrow U \rightarrow G.
]

Where:

* (D) is ecological telemetry;
* (P) is the projector;
* (U) is the task-scoped clamp constellation;
* (G) is the Grid81 structural state.

The ecology must never write Grid81 directly.

The projector must remain the only path from ecological consequence to structural proposal.

The future TRM adapter must remain ignorant of:

* resources;
* fitness;
* lineage;
* ecological state;
* frame verdicts;
* error reports;
* climate gradients.

It may receive only its approved structural inputs.

These are intended invariants, not current end-to-end behavior.

---

## XIII. Contradiction and underdetermination

The target architecture distinguishes:

### Contradiction

Available constraints are mutually incompatible, or the current frame indicates that changed structural constraints may be required.

### Underdetermination

Required evidence is absent, so no justified clamp constellation can resolve the meta-task.

The present code does not operationally classify either condition.

`projector/gaps.py` is an early prototype and must not be treated as a qualified gap detector.

Underdetermination is not currently a `FrameVerdict`.

A future gap mechanism must bind missing topology to declared evidence slots and user-facing questions. It must not infer semantic missing information from ecological state alone.

---

## XIV. Determinism and replay

The current implemented substrate has demonstrated deterministic behavior under:

```text
PYTHONHASHSEED=0
PYTHONHASHSEED=1
PYTHONHASHSEED=717
```

The demonstrated deterministic artifacts include:

* geometry lookup construction;
* climate-sidecar state;
* resource diffusion;
* ecological state digests;
* ecological transaction telemetry;
* frame assessment digests;
* meta-episode state digests;
* arrangement-probe output.

The current package contains chained canonical ecological frame records and exact single-frame replay verification.

Every frame record binds:

- input ecological-state digest;
- output ecological-state digest;
- climate digest;
- transition-age digest;
- neighbor-table digest;
- ecological configuration digest;
- deterministic runtime-policy digest;
- telemetry digest;
- previous frame-record digest.

The arithmetic policy is process-global and explicitly enforced:

- Torch intra-op threads: 1
- deterministic algorithms: enabled
- MKLDNN: disabled

The policy was required because byte-identical ecological state did not initially guarantee byte-identical telemetry under parallel reduction kernels. Serial final reduction alone was insufficient; the kernel-execution policy itself had to be constrained and ledger-bound.

The package has demonstrated exact single-frame replay across separate Python processes under hash seeds `0`, `1`, and `717`.

It does not yet persist every input tensor required to reconstruct a complete multi-frame episode from the ledger alone. Full episode archival and autonomous multi-attempt replay are qualified for registered deterministic adapters; production-TRM reconstruction remains unqualified.

The target standard remains:

> A full frame that cannot be reproduced from its initial snapshot, event stream, versions, and seeds must not be treated as qualified evidence.

---

## XV. Evaluation posture

The visualizer will eventually be persuasive whether or not the TRM contributes useful structure.

Spatial fronts, resource blooms, collapses, and corridors can all look meaningful in an unqualified simulation.

The required future ablation remains:

### Arm A

Persistent non-Grid state machine.

### Arm B

Persistent Grid81 climate with direct clamp injection and no TRM relaxation.

### Arm C

Persistent Grid81 climate after frozen-TRM reconciliation.

Only the comparison between Arms B and C can determine whether Sudoku reconciliation contributes beyond direct projected climate assignment.

The arrangement probe has already established that spatial arrangement matters before the TRM is involved.

It has not established that the TRM chooses better arrangements.

---

## XVI. Experimental evaluation utilities

`evaluation/cascade_graph.py` currently provides an experimental state-conditioned effect store and calibration helpers.

No real TRM cascades have yet qualified it.

Its edges must not be treated as a causal prior until the same clamp is tested across multiple Grid81 contexts and the resulting effects demonstrate generalization.

Until then, it is per-episode telemetry infrastructure.

The NSI corruption weight (\lambda) remains unset.

It must be calibrated from a baseline such as Arm B rather than declared as an untethered safety constant.

---

## XVII. Restraint as design

The current ecology intentionally excludes:

* neural components;
* transformer entities;
* learned climate decoders;
* semantic digit tables;
* explicit expert-routing logic;
* model selection;
* adapter selection;
* runtime activation;
* autonomous structural writes.

The current mechanisms are limited to:

* three component types;
* continuous climate response;
* local genome adaptation;
* resource production and consumption;
* structural carrying-capacity support;
* gradient-conditioned field diffusion;
* directed transition shock;
* deferred death;
* bounded deterministic transactions.

This restraint is necessary for causal attribution.

Any observed behavior should have as few candidate explanations as possible.

---

## XVIII. Relationship to the G5 authority chain

G5.3A defines a future contract for atomic single-use capability consumption producing one inert, unapplied structural-influence artifact and one receipt.

The Darwinian Matrix does not currently implement that transaction.

Specifically, it does not:

* consume a G5.2B capability;
* transition a canonical capability to `CONSUMED`;
* produce a G5.3A structural-influence artifact;
* produce a G5.3A receipt;
* apply structural influence;
* select a runtime consumer;
* target an ECS entity;
* activate a model or adapter.

Any future connection between Darwinian telemetry and the G5 authority chain requires a separate qualified implementation and cannot be inferred from G5.3A contract existence.

---

## XIX. Current falsifiable claims

The current code supports the following checkable claims:

1. The 81×81 lattice maps exactly to 81 regions of 81 sites.
2. Climate storage is separate from ecological storage.
3. Ecology cannot mutate the climate sidecar through its supplied views.
4. Exact Grid81 validation rejects sum-preserving invalid grids.
5. Directed transitions distinguish (a\rightarrow b) from (b\rightarrow a).
6. Resource diffusion uses separate read and write buffers.
7. Internal patch borders remain ecologically contiguous.
8. Climate gradients alter edge permeability.
9. Rising and falling transitions produce different ecological effects.
10. Producer, consumer, and structure components have distinct transaction behavior.
11. Ecological input state is not mutated by a successful transaction.
12. Invalid and non-finite state is rejected.
13. Attempt budgets are enforced.
14. Frame trajectories distinguish improvement, degradation, stalling, and oscillation.
15. Fixed Sudoku climate marginals do not imply fixed ecological opportunity.
16. The implemented probes are deterministic under the tested hash seeds.

The current code does not yet support claims about:

* TRM-generated climate improvement;
* autonomous problem resolution;
* semantic understanding;
* clarification quality;
* safe expert selection;
* superior routing;
* end-to-end replay;
* activation authority.

---

## XX. The standard

The Darwinian Matrix is intended to become a falsifiable structural-control experiment.

Its value does not come from appearing alive.

Its value comes from making each architectural claim separable and testable:

```text
geometry before ecology
ecology before TRM coupling
TRM coupling before feedback
feedback before authority
authority before activation
```

The current substrate has qualified geometry, climate ownership, persistent transition-age semantics, deterministic ecological mechanics, bounded transaction behavior, chained frame records, exact single-frame replay, frame assessment, and arrangement sensitivity.

The production TRM, projector loop, clamp lifecycle, full episode archive, autonomous multi-frame replay, and authority integration remain ahead.

Failure at any later layer must remain visible rather than being absorbed into a persuasive visualization or renamed as emergence.

## Implemented Episode Ownership Contract

The current controller now owns a persistent immutable-by-interface Darwinian episode envelope.

The envelope binds:

- the current solved Grid81;
- projector clamp state;
- persistent climate state;
- ecological state;
- meta-episode state;
- structural-attempt index and budget;
- ecology-record chain head;
- frame-commit chain head;
- structural-attempt chain head;
- terminal episode disposition.

A rejected structural refinement consumes a unique structural-attempt index but does not advance the ecological frame index, climate state, ecological state, or meta-episode attempt count.

An accepted structural refinement advances both the structural-attempt index and the committed ecological frame count.

The episode closes deterministically when either:

- the meta-episode reaches a terminal verdict; or
- the structural-attempt budget is exhausted.

Episode closure releases every task-scoped clamp through an explicit clamp transaction and binds the resulting close receipt.

The implemented episode envelope does not yet persist every tensor and configuration required for autonomous reconstruction from disk. Full episode archival and autonomous multi-attempt replay are qualified for registered deterministic adapters; production-TRM reconstruction remains unqualified.

## Implemented Full Episode Archive

The Darwinian Matrix now implements a self-contained deterministic episode archive.

The archive persists:

- the complete initial solved Grid81;
- projector clamp state;
- persistent climate state;
- ecological component tensors;
- meta-episode state;
- structural-attempt and ecological-frame chain heads;
- ecological transaction configuration;
- neighbor topology;
- region map;
- target viability;
- convergence parameters;
- per-attempt random seeds;
- per-attempt adapter reconstruction specifications;
- structural-attempt, refinement-result, state-transition, and terminal clamp-release digests.

A complete archived episode can be loaded from disk and replayed without caller-supplied runtime state.

The qualified replay sequence includes both:

- rejected structural refinements that consume structural-attempt budget without advancing ecological time; and
- accepted structural refinements that advance climate, ecology, frame assessment, and meta-episode state.

The archive was qualified across separate Python processes under `PYTHONHASHSEED=0`, `1`, and `717`.

The qualified three-attempt probe produced byte-identical archives of 437169 bytes and reconstructed:

- three structural attempts;
- two committed ecological frames;
- one terminal episode;
- zero replay failures.

The autonomous replay registry currently contains only the deterministic Sudoku reference adapter.

Therefore the current implementation establishes the archive and replay mechanism, but it does not yet establish autonomous reconstruction or replay of the production frozen TRM.
