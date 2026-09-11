# Elpis

**A deterministic structural-reasoning architecture for bounded learned proposals, explicit authority, and falsifiable runtime composition.**

**Release line: Elpis2.1.23**

Elpis is a systems-research project about a narrow question: can learned components contribute useful structural proposals while deterministic machinery retains ownership of representation, admissibility, authority, validation, and terminal action?

The repository is intentionally decomposed. It contains several qualified public surfaces that coexist under one release boundary but are **not automatically one runtime pipeline**: typed semantic and Grid81 control machinery, bounded learned structural guidance, native lexical/retrieval components, historical offline runtime integrations, a runnable public FPRM reference-model path, a separately frozen ECS Structural Authority R0 contract, and release/provenance enforcement.

That decomposition matters. A component can be present, qualified, and useful without being runtime-admitted into every other component. Evidence can establish a mechanism without granting that mechanism authority. A proposal can improve without becoming executable. A structural contract can be public and executable while still lacking a qualified semantic binding into another subsystem.

Elpis therefore presents itself as a falsifiable research artifact rather than a general intelligence claim. It does **not** claim solved alignment, trusted natural-language understanding, general Grid81 satisfiability, unrestricted autonomous execution, autonomous implementation synthesis, cross-process attestation, AGI, or ASI.

## Release Notes

**Elpis2.1.23** consolidates the public ECS surface and publishes the closed Branch35–40 scientific evidence without rewriting its bytes. The root release-note files are also consolidated into a single archive.

- Current notes: [`RELEASE_NOTES/Elpis2.1.23.md`](RELEASE_NOTES/Elpis2.1.23.md)
- Release-note archive: [`RELEASE_NOTES/`](RELEASE_NOTES/)
- ECS authority and science: [`ECS/`](ECS/)

## Install and quick start

The Python distribution project name is **`elpisai`**. The console command remains **`elpis`**, and the existing Python import-package names remain unchanged.

The PyPI name `elpis` belongs to an unrelated project. Do **not** use `pip install elpis` to obtain this repository.

### From a source checkout

Base installation uses only the base dependency set:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

The learned/reference-model path requires the optional `trm` extra:

```bash
python -m pip install ".[trm]"
```

### From PyPI

For a release that is available on PyPI, the distribution commands are:

```bash
python -m pip install elpisai
python -m pip install "elpisai[trm]"
```

PyPI publication is release-specific. If the requested version is not present on PyPI, install from the corresponding tagged source checkout rather than substituting the unrelated `elpis` distribution.

### Reference-model example

With the `trm` extra installed:

```bash
elpis model fetch
elpis model verify

elpis sudoku solve \
  --puzzle '.34678912672195348198342567859761423426853791713924856961537284287419635345286179' \
  --device cpu
```

The reference runtime verifies the pinned model identity and state ABI before loading. This demonstrates a reproducible model-integrity and Sudoku inference path. It does not establish generalized reasoning: **Sudoku capability is evidence of Sudoku capability.**

---

## 1. Research question

The central question is:

> **Can a learned component contribute useful structural search, proposal, or ordering information while a deterministic substrate retains ownership of representation, admissibility, authority, validation, and terminal action?**

Let `x` denote a typed request, `S` a structural state, `M` a learned proposer, `p = M(x, S)` a proposal, and `J` a deterministic adjudicator operating under an explicit contract `C`. The intended separation is:

```math
\begin{aligned}
p &= M(x,S),\\
S' &= J(x,S,p;C).
\end{aligned}
```

`M` must not be able to redefine `C`, widen its writable scope, grant itself capability, convert confidence into permission, or treat its own output as proof of admissibility.

Elpis uses **authority** operationally: the explicit capability to admit, reveal, consume, mutate, validate, execute, or otherwise advance a state transition. Authority is not synonymous with model confidence, heuristic usefulness, semantic plausibility, provenance evidence, or a successful test result.

Four separations recur throughout the project:

1. **Representation is not proposal.** A learned component does not silently own the task representation it later proposes against.
2. **Proposal is not admissibility.** Candidate material is not accepted merely because a model or producer emitted it.
3. **Validation is not execution.** A source artifact may pass a static policy while execution authority remains false.
4. **Evidence is not capability.** Receipts, digests, witnesses, and terminal results can prove bounded facts without becoming reusable permission.

---

## 2. Repository architecture: multiple bounded surfaces

The current public repository should not be read as one monolithic agent loop. Its major surfaces are better represented as follows:

```math
\begin{array}{c}
\boxed{\mathrm{ELPIS}}
\\[1em]
\begin{array}{ccc}

\boxed{
\begin{array}{c}
\text{Native semantic / retrieval}\\
\text{substrate}\\[0.35em]
\text{Streaming Regex}\\
\text{HACF retrieval}\\
\text{Query-local ingress}\\
\text{Semantic Spine}
\end{array}
}

&

\boxed{
\begin{array}{c}
\text{Structural control / guidance}\\
\text{path}\\[0.35em]
\text{Semantic IR}\\
\text{Deterministic Projector}\\
\text{Grid81}\\
\text{TRM guidance}\\
\text{P1 / adjudication}\\
\text{Validated-source path}
\end{array}
}

&

\boxed{
\begin{array}{c}
\text{Reference-model}\\
\text{path}\\[0.35em]
\text{FPRM authority}\\
\text{Pinned checkpoint}\\
\mathrm{elpis\ CLI}\\
\text{Sudoku inference}
\end{array}
}

\end{array}
\\[1em]
\Downarrow
\\[-0.1em]
\boxed{\text{Explicit authority / capability boundaries}}
\\[1.2em]
\begin{array}{ccc}

\boxed{
\begin{array}{c}
\text{ECS Structural Authority R0}\\[0.25em]
\text{Separate frozen structural contract}\\
\text{not silently identified with}\\
\text{Grid81 or Semantic IR}
\end{array}
}

&

\boxed{
\begin{array}{c}
\text{Historical runtime integrations}\\[0.25em]
\mathrm{runtime/R0}\\
\mathrm{runtime/R1}\\
\text{Earlier qualified offline compositions}
\end{array}
}

&

\boxed{
\begin{array}{c}
\text{Release / provenance authority}\\[0.25em]
\text{Manifests}\\
\text{Verifier and mutation tests}\\
\text{CI, tags, and releases}
\end{array}
}

\end{array}
\end{array}
```

**Repository coexistence does not imply runtime integration.** This is especially important for ECS Structural Authority R0, the native ingress components, canonical Grid81 state, historical R0/R1 integrations, and the public reference-model path.

### 2.1 Canonical public component registry

`manifests/PUBLIC_COMPONENT_REGISTRY.json` is the repository's public registry for the current canonical assembly surface. It lists 16 public components and marks their component-level `runtime_admission` false. That field must not be silently converted into a stronger whole-system deployment claim.

The registered public components are:

| Component | Public path | Role / boundary |
|---|---|---|
| [`HACF_R3`](native/hacf/README.md) | `native/hacf/` | Native deterministic HACF substrate. |
| [`Semantic_Structural_Spine_V1`](native/semantic-spine/README.md) | `native/semantic-spine/` | Native semantic/structural spine over HACF. |
| [`Grid81_Structural_Semantics`](components/Grid81StructuralSemantics/README.md) | `components/Grid81StructuralSemantics/` | Typed structural semantics for the Grid81 family. |
| [`Grid81_Typed_Projection_Compiler`](components/Grid81TypedProjectionCompiler/COMPONENT_MANIFEST.json) | `components/Grid81TypedProjectionCompiler/` | Deterministic typed projection. |
| [`G50b_Structural_Group_Projection_Compiler`](components/Grid81StructuralGroupProjectionCompiler/README.md) | `components/Grid81StructuralGroupProjectionCompiler/` | Structural group projection. |
| [`Grid81_Canonical_Substrate`](components/Grid81/README.md) | `components/Grid81/` | Read-only canonical Grid81 generation substrate. |
| [`TRMFractalSpine_Structural_Modules`](components/TRMFractalSpine/README.md) | `components/TRMFractalSpine/` | Structural TRM contracts/refinement surfaces. |
| [`G51b_Deterministic_Structural_Adjudicator`](components/Grid81DeterministicStructuralAdjudicator/README.md) | `components/Grid81DeterministicStructuralAdjudicator/` | Deterministic structural adjudication. |
| [`DarwinianMatrix`](components/DarwinianMatrix/README.md) | `components/DarwinianMatrix/` | Structural clamp, Projector, and bounded refinement mechanisms. |
| [`P0ControlProtocol`](components/Pipeline/P0ControlProtocol/README.md) | `components/Pipeline/P0ControlProtocol/` | P0 control, Semantic IR, projection, and validation contracts. |
| [`elpis_header`](native/elpis-header/src/elpis_header/observer/README.md) | `native/elpis-header/` | Native/header-side Grid81 runtime observation contract. |
| [`G52b_Capability_Authority_Evaluator`](components/Grid81DeterministicCapabilityAuthorityEvaluator/COMPONENT_MANIFEST.json) | `components/Grid81DeterministicCapabilityAuthorityEvaluator/` | Capability authority evaluation. |
| [`G53b_Capability_Consumption_Compiler`](components/Grid81DeterministicCapabilityConsumptionCompiler/COMPONENT_MANIFEST.json) | `components/Grid81DeterministicCapabilityConsumptionCompiler/` | Capability-consumption compilation. |
| [`G53c_Capability_Application_Executor`](components/Grid81DeterministicCapabilityApplicationExecutor/COMPONENT_MANIFEST.json) | `components/Grid81DeterministicCapabilityApplicationExecutor/` | Bounded capability application. |
| [`G53e_Canonical_Promotion_Planner`](components/Grid81DeterministicCanonicalPromotionPlanner/COMPONENT_MANIFEST.json) | `components/Grid81DeterministicCanonicalPromotionPlanner/` | Canonical promotion planning; not an in-repository canonical-state writer. |
| [`CNumPyCortex`](components/CNumPyCortex/README.md) | `components/CNumPyCortex/` | Optional telemetry-to-Grid81 transport/recursion surface. |

The internal canonical manifest also retains historical/canonical identities that are not all physically shipped as public components. Public repository descriptions should use the public registry when stating what is actually shipped.

### 2.2 Additional qualified ingress components

The repository also contains qualified successor components that are not represented as entries in the 16-component public registry and therefore should be described separately rather than smuggled into the canonical assembly claim.

`StreamingRegexIngress` provides a bounded native lexical producer with a stable C-compatible ABI. Its successful v1 profile requires `carry_bytes >= 256` and `data_len <= carry_bytes`; it does not claim arbitrary-length incremental-regex completeness. Output remains `PROPOSED_UNADMITTED`.

`RegexHACFQueryIngress` composes bounded Regex ingress, native HACF lookup, provenance-bound proposal construction, and query-local publication. It does not mutate the persistent Semantic Fabric, admit semantic truth, map semantics to Grid81, or authorize execution.

`QueryLocalProposalIngress` materializes provenance-bound proposal envelopes into an atomic private query overlay. Failure publishes neither overlay nor receipt. Proposal material remains `PROPOSED_UNADMITTED`; semantic, admission, execution, and runtime authority remain zero.

These components are useful evidence of bounded composition, but their presence does not imply general runtime admission.


### 2.3 Post-2.1.16 canonical-writer engineering successor

The released **Elpis2.1.16** public component registry remains the 16-component
surface above. The following components were qualified later on the local
successor engineering lineage and are **not yet entries** in
`manifests/PUBLIC_COMPONENT_REGISTRY.json`:

- [`Grid81DeterministicCanonicalPromotionAuthority`](components/Grid81DeterministicCanonicalPromotionAuthority/README.md) — converts an advisory promotion decision plus explicit external operator-approval binding into a deterministic one-use `ATOMIC_GRID81_CANONICAL_PROMOTION` capability. The approval digest is a binding, not a digital-signature or human-authentication claim.
- [`Grid81DeterministicCanonicalCandidateConstructor`](components/Grid81DeterministicCanonicalCandidateConstructor/README.md) — constructs a complete isolated immediate-successor canonical candidate while leaving live canonical state and the publication ledger untouched.
- [`Grid81DeterministicCanonicalPublisher`](components/Grid81DeterministicCanonicalPublisher/README.md) — performs authority-gated atomic publication with durable publication-ledger reservation, exact replay handling, historical-generation preservation, and production-reader post-verification.

The application-executor component also now contains a durable SQLite-backed
application ledger used for cross-process publication reservation. The
repository-level writer-chain regression composes promotion authority,
candidate construction, durable reservation, atomic publication, and the
production reader in one bounded transaction.

These successor components do not broaden model authority, do not authorize
ECS world mutation, and do not make canonical mutation a background runtime
behavior. Canonical publication remains an explicitly authorized transaction.


---

## 3. Structural-control path

### 3.1 Canonical relational Semantic IR

`P0SemanticRequestV1` is a canonical relational task representation independent of Grid81. It can represent entities, operations, constraints, relations, dependencies, quantities, and declared outputs with canonical identifiers, validation rules, serialization, and digest-bound identity.

It does **not** parse natural language. It does not, by itself, establish a complete semantic mapping into Grid81. C2R7-A established the relational graph contract; C2R7-B binds that graph's identity as a sidecar through the structural path while preserving the distinction between semantic identity and Grid81 structural meaning.

Trusted natural-language -> Semantic IR compilation remains unqualified.

### 3.2 Grid81

Grid81 is an explicit bounded structural control space. The current P0 projection family uses an 81-cell topology organized as nine ranks across nine lanes with typed structural state, lane/rank/locus relations, invariants, writable/frozen boundaries, residual state, semantic sidecar identity, deterministic traces, and digest-bound output.

The earlier C2R6-P0 greedy rank/locus allocator was independently shown incomplete over its bounded audited `ROUTE`/`state_feeds` subset by FuryanLocusOracle R0. That historical defect is **not a current frontier item**: Elpis2.1.8 replaced the incomplete strategy with deterministic joint finite-domain rank/locus allocation and differentially qualified the supported subset against Furyan's 44,005-case canonical core.

The successor allocator also carries a deterministic search-entry budget. `SEARCH_BUDGET_EXHAUSTED` is distinct from UNSAT or decomposition. The bounded qualification is not a theorem of universal Grid81 satisfiability.

### 3.3 Canonical Grid81 runtime remains read-only; promotion is explicit

The released **Elpis2.1.16** public runtime boundary remains read-only: it ships
canonical generation `000001`, a production reader, and a runtime reducer, and
it does not ship the post-2.1.16 writer-chain components described above.

On the successor engineering lineage, a qualified in-repository canonical
writer chain now exists, but it is deliberately separated from normal runtime
consumption:

```text
G5.3B/C/D evidence
        |
        v
G5.3E advisory promotion plan
        |
        v
explicit promotion authority
        |
        v
one-use ATOMIC_GRID81_CANONICAL_PROMOTION capability
        |
        v
isolated candidate constructor
        |
        v
durable publication-ledger reservation
        |
        v
atomic canonical publisher
        |
        v
production-reader verification
```

The promotion planner remains non-executable and non-authoritative. The
promotion-authority component requires an explicit external operator-approval
digest and does not claim that the digest authenticates a human or constitutes
a digital signature. The candidate constructor does not mutate live canonical
state or consume the publication ledger. The publisher requires the exact
promotion capability, rejects stale or mismatched authority, preserves prior
generation bytes, reserves durable one-use publication state, performs atomic
directory exchange, and verifies the committed result through the production
reader.

The historical `.authority_audit.json` remains historical evidence rather than
independent proof of its own claims. Likewise, the original process-local
`ApplicationLedger` should not be confused with the later durable publication
ledger.


### 3.4 Bounded learned structural guidance

The qualified learned structural-guidance path keeps the model behind an explicit request-level gate that defaults OFF. The admissible checkpoint identity is pinned while the host supplies the checkpoint path. The semantic binding envelope remains outside model input. Model authority is zero.

Candidate legality and transition execution remain deterministic. The frozen TRM can affect bounded proposal/search ordering only inside an already admitted space. Failure to admit guidance returns explicit fallback control rather than silently widening the model's authority.

### 3.5 Authority-preserving improvement witness

Elpis2.1.11 added the closed Authority-Preserving Improvement Witness R0 (APW R0). Its bounded deterministic fixture demonstrates proposal quality improving exactly as the literal witness `27 -> 54 -> 81/81`:

```math
27 \;\longrightarrow\; 54 \;\longrightarrow\; 81/81
```

across three proposal cycles while proposer authority, feedback authority, and accumulated authority remain zero.

The positive terminal fixture is built through public Semantic IR, deterministic P0 projection, and P1-owned transition authority. Exactly one P1-legal strict improvement is certified on the `MUTATION_HAZARD` fixture (`cost 1 -> 0`). The same final proposal packet presented to an already-optimal fixture yields explicit abstention.

This is evidence that repeated proposal improvement can coexist with authority separation. It is **not** a claim of autonomous self-improvement, generalized competence, arbitrary learned-model safety, or execution authority.

### 3.6 Validated-source composition

The public structural-guidance runtime under `src/elpis_reference/structural_guidance/` composes already-qualified stages into a terminal static-validation result:

```math
\begin{aligned}
\mathrm{Semantic\ IR}
&\longrightarrow \mathrm{Deterministic\ structural\ projection}\\
&\longrightarrow \mathrm{Bounded\ guidance\ admission}\\
&\longrightarrow \mathrm{Resolved\ topology}\\
&\longrightarrow \mathrm{Zero\!-\!authority\ observation}\\
&\longrightarrow \mathrm{One\!-\!shot\ materialization}\\
&\longrightarrow \mathrm{Deterministic\ planning}\\
&\longrightarrow \mathrm{Decoder\!-\!plan\ normalization}\\
&\longrightarrow \mathrm{Deterministic\ source\ construction}\\
&\longrightarrow \mathrm{Canonical\ Python\ AST\ policy}\\
&\longrightarrow \mathrm{Authority\!-\!zero\ terminal\ result}.
\end{aligned}
```

The composition binds major intermediate identities and emitted-source digest. Terminal results retain:

```text
authority_granted     == 0
validation_authorized == false
execution_authorized  == false
```

No generated source is executed by this path.

---

## 4. Static Python policy and the implementation-synthesis boundary

Elpis contains a canonical static Python AST policy used by the validated-source path. The policy rejects imports, ambient scope mutation, classes, decorators, `with`/`async with`, indirect call surfaces, unapproved attributes, selected introspection families, and other bounded prohibited forms. Canonical restrictions are non-subtractive.

A result of:

```text
validation_code = AST_VALID
```

means only that source parsed and passed the configured static policy. It does **not** establish functional correctness, task fidelity, sandbox safety, or permission to execute.

A separate blind `merge_intervals` experiment made this boundary concrete: the composition produced AST-valid source while all 7/7 functional checks failed because the emitted function returned `None`. A known-correct positive-control body passed the same downstream source/functional-validation path.

Therefore autonomous implementation synthesis remains unqualified even when upstream semantic, structural, materialization, planning, source, and static-validation mechanisms are functioning.

The synchronous-language closure is also not complete. Undecorated async functions, `await`, async iteration, generators, and `yield`/`yield from` do not yet have a fully resolved synchronous-language contract in the canonical policy.

---

## 5. ECS Structural Authority R0

Elpis2.1.12 published and sealed a separate prospectively defined ECS structural contract:

```text
MICROSCOPIC_COLUMN_PARTICIPATION_MASK_R0
```

The contract applies to a frozen cubic ECS reference family. It treats microscopic column slots as operational gauge addresses rather than intrinsic semantic entities.

For each exact nonzero frozen whole column, the writable structural state is binary:

```text
ACTIVE
DISABLED
```

Exact-zero frozen columns are:

```text
FROZEN_ZERO
```

and are non-writable.

The mutation grammar is limited to:

```text
ABSTAIN
DISABLE_COLUMN
RESTORE_COLUMN
```

`DISABLE_COLUMN` materializes six exact binary64 positive-zero values in the existing slot without changing width. `RESTORE_COLUMN` reproduces the exact retained frozen column bytes. Continuous column bytes, primitive law, and width remain frozen.

Column indices are operational addresses. Simultaneously permuting frozen columns and their participation statuses is an equivalence. `S3` is an external scientific observation and is **not** edit identity. No pairwise graph, adjacency, or module structure is introduced by this authority.

### 5.1 Executable authority and fail-closed installed behavior

Elpis2.1.13 made the published R0 contract executable through `elpis_reference.ecs_r0` while retaining explicit authority ownership.

Installed-package behavior remains fail-closed. If no explicit authority root is supplied and no valid source-colocated authority is available, the installed runtime raises:

```text
AUTHORITY_ROOT_REQUIRED
```

Repository-owned tests/tools bind repository authority explicitly. The package must not invent authority or rely on broad source-tree `PYTHONPATH` compensation to make installed-package tests pass.

### 5.2 E0R2 diagnostic

The bounded executable E0R2 diagnostic is closed at:

```text
SEMANTIC_IR_INSUFFICIENT
```

The unresolved object is one writable whole-column participation primitive: a binary structural referent bound to the external frozen sidecar and operational gauge slot with deterministic DISABLE/RESTORE semantics while exact-zero slots remain frozen.

This result does **not** invalidate the Structural Authority R0 ontology. It says the existing Semantic IR does not yet provide the required executable writable referent.

E1 and E2 have not executed. Learned, Darwinian, and scientific execution are not authorized by this result.

---

## 6. Native semantic and retrieval surfaces

The `native/` tree contains public C/C++ substrate work including HACF, the HACF bridge, Semantic Structural Spine, and the Elpis header integration. These are not all required by the base Python/reference install and should not be described as a single stable native deployment ABI.

Current public qualification supports the HACF native path on Linux and macOS through the existing build branches. Windows native HACF is not qualified by the current public evidence.

The native surface and bounded Regex/HACF ingress components are useful because they demonstrate another version of the same architectural discipline: lexical/retrieval evidence may be produced and composed without automatically gaining semantic truth, Grid81 mapping, or execution authority.

For host-capability inspection use the repository setup tooling rather than copying historical runtime build commands blindly:

```bash
python tools/setup.py --profile full --dry-run
```

Compiled native artifacts are build products, not repository authority.

---

## 7. Historical offline runtime integrations

`runtime/R0/` and `runtime/R1/` preserve historical qualified offline integration layers. They are **not equivalent** to the current top-level learned reference runtime under `src/elpis_reference/`.

R0 composes a deterministic structural transaction approximately of the form:

```text
RequestContext
-> P0 projection
-> Grid81 / scope
-> StructuralOracle
-> adjudication
-> Darwinian episode
-> deterministic decoder
-> AST validator
-> receipt
```

R0 deliberately excluded learned-model inference when it was qualified.

R1 prepends bounded read-only HACF retrieval/evidence and delegates the structural transaction to R0.

These directories are retained for reproducibility and architectural history. Their component-local commands may reflect the environments in which they were originally qualified and are not the current universal setup interface.

---

## 8. Public reference-model path

The public FPRM reference path is separate from the frozen structural-guidance TRM research path. It exists to prove that a pinned public model can be fetched, verified, strictly loaded, and executed for a real task.

The Python package carries FPRM authority/configuration data and verifies model identity and ABI before loading. The current public example is CPU Sudoku inference.

The reference path does not convert the model into an authority root and does not establish general reasoning. Model performance on Sudoku must not be used as evidence for unrelated semantic, structural, coding, or agent capability.

---

## 9. Distribution and installed-artifact contract

The distribution rename is intentionally narrow:

```text
PyPI / distribution project: elpisai
console command:              elpis
Python import API:            unchanged
```

Base package dependencies are NumPy and SciPy. Torch and the model-oriented dependencies are under the explicit `trm` extra; the package does **not** have a hard base Torch dependency.

The intended installed import surfaces include:

```text
elpis
elpis_reference
DarwinianMatrix
elpis_p0
elpis_fractal_spine
elpis_grid81_semantics
elpis_grid81_typed
elpis_grid81_groups
elpis_grid81_adjudication
elpis_grid81_capability_authority
elpis_grid81_consumption_compiler
elpis_grid81_application_executor
elpis_grid81_promotion_planner
c_numpy_cortex
elpis_header
elpis_runtime_r0
elpis_runtime_r1
```

Installed-artifact qualification must distinguish source-tree imports from package imports. A clean installed-package check should establish that intended surfaces are absent before installation, resolve from `site-packages` afterward, report distribution metadata under `elpisai`, preserve the `elpis` console entry point, and keep installed ECS authority fail-closed unless explicit authority is supplied.

---

## 10. Qualified claim surface

“Qualified” below means that the repository carries an implementation and bounded evidence for the stated mechanism. It does not widen the claim beyond that mechanism.

| Capability | Qualified claim | Boundary |
|---|---|---|
| Canonical relational Semantic IR | Typed relational requests can be validated, canonicalized, and digest-bound. | No trusted natural-language parser. |
| Semantic identity propagation | Relational semantic-request identity can propagate as a bound sidecar through the structural path. | Does not establish a complete graph-to-Grid81 semantic mapping. |
| Semantic -> Grid81 projection | Supported structure is deterministically projected under pinned rules with typed outcomes and replay evidence. | No universal Grid81 satisfiability theorem. |
| Joint rank/locus allocator | The repaired allocator matches the frozen Furyan oracle over the bounded 44,005-case canonical core. | Bounded audited model only; budget exhaustion remains distinct. |
| Structural TRM guidance | A pinned model can influence bounded proposal/search ordering when explicitly admitted. | Gate defaults OFF; model authority remains zero. |
| Deterministic adjudication | Candidate legality and transition ownership remain in deterministic machinery. | Does not imply arbitrary task correctness. |
| APW R0 | Repeated proposal quality can improve in the closed witness while proposer/feedback authority remains zero. | Not autonomous self-improvement or execution authority. |
| Materialization / planning / decoding | Bound stage transitions can carry structural results through explicit one-shot authority objects. | Stage authority is not ambient or reusable. |
| Static Python validation | Source can be checked against the canonical bounded AST policy. | AST validity is not functional correctness, sandboxing, or execution permission. |
| Terminal validated-source result | The structural-guidance composition emits digest-bound authority-zero terminal results. | Generated source does not execute. |
| FuryanLocusOracle R0 | A frozen independent finite-placement oracle can decide the admitted bounded model and produce checkable certificates. | Not a general Grid81 solver and not runtime authority. |
| ECS Structural Authority R0 | Whole-column ACTIVE/DISABLED/FROZEN_ZERO participation and exact restore semantics are publicly specified and executable. | No Grid81/Semantic-IR representability or efficacy claim. |
| E0R2 | The existing Semantic IR is insufficient for the required ECS writable-participation primitive. | Bounded diagnostic; E1/E2 remain unexecuted. |
| Native Regex/HACF query ingress | Bounded lexical/retrieval/proposal composition can preserve provenance while retaining zero admission/execution authority. | Not semantic truth or runtime admission. |
| Public FPRM reference path | A pinned model can be fetched, verified, loaded, and used for real CPU Sudoku inference. | Sudoku evidence only. |
| Release integrity | Release declarations, manifests, mutation guards, public verification, CI, tag, and release gates can bind exact public artifacts. | A development tree is not a sealed release. |

Negative results are part of the claim surface. A neighboring mechanism becoming green does not promote another mechanism to a stronger claim.

---

## 11. Known limitations and explicit nonclaims

Elpis currently makes no claim of:

- trusted natural-language -> Semantic IR compilation;
- a complete semantic mapping from relational Semantic IR into every Grid81 structural degree of freedom;
- executable Semantic-IR representation of the ECS R0 writable participation primitive;
- E1 or E2 execution under the ECS program;
- general autonomous implementation synthesis;
- generated-source execution authority;
- arbitrary autonomous tool execution;
- general Grid81 satisfiability;
- universal allocator completeness outside the qualified bounded model;
- a qualified in-repository writer for canonical Grid81 generations/HEAD;
- cross-process one-time capability consumption;
- cross-process or asymmetric receipt attestation;
- hostile same-process isolation;
- unrestricted learned-model authority;
- runtime admission merely because a component appears in the repository;
- generalized held-out competence unless separately qualified;
- learned/Darwinian/scientific efficacy from the existence of the ECS structural contract;
- solved alignment;
- AGI or ASI; or
- performance improvement not demonstrated by qualification.

These are architectural boundaries, not rhetorical disclaimers attached after the fact.

---

## 12. Current research frontier

The current frontier is defined by unresolved mechanisms, not by old defects that have already been repaired.

### 12.1 ECS writable-participation semantics

The immediate bounded ECS architectural blocker is E0R2's `SEMANTIC_IR_INSUFFICIENT` result. A future successor must introduce or qualify the missing writable whole-column participation referent without silently changing frozen ECS authority, inventing graph semantics, or treating `S3` as edit identity.

Any Semantic-IR <-> ECS binding must preserve the R0 operational-gauge equivalence and exact frozen-sidecar semantics.

### 12.2 E1 / E2 remain gated

E1 and E2 have not executed. They should not become authorized merely because documentation, packaging, or unrelated runtime tests are green.

### 12.3 Trusted semantic compilation

Natural-language -> canonical relational Semantic IR remains open. A future learned compiler would need independent validation of task representation and must not become self-authorizing merely by producing a plausible graph.

### 12.4 Functional implementation synthesis

The validated-source path has already demonstrated that AST-valid source can be functionally wrong. Any future implementation-synthesis claim therefore requires independent functional evidence in addition to syntax/policy validity.

### 12.5 Authority durability and external attestation

Current security/capability evidence is deliberately bounded. Cross-process durable consumption, asymmetric/external attestation, and hostile same-process isolation remain separate research problems and should not be inferred from deterministic digests or process-local ledgers.

### 12.6 Static-language closure

The canonical Python policy still has unresolved synchronous-language disposition for async/generator forms. Closing that boundary is a policy-definition task distinct from implementation synthesis or execution sandboxing.

### 12.7 Runtime composition and admission

The repository now contains more qualified surfaces than the original README paper described. Future integration work should make connections explicit and independently qualified rather than equating directory presence, canonical registration, build-system admission, or historical integration with current runtime admission.

### 12.8 Learned / Darwinian refinement

Learned and Darwinian refinement remain bounded research paths. APW R0 shows that proposal improvement can coexist with zero proposer authority, but broader search/evolution layers must not move semantic ownership, transition legality, or execution authority into the proposer.

---

## 13. Repository organization

The repository contains several distinct authority and implementation roots:

| Path | Role |
|---|---|
| `src/elpis_reference/` | Portable public reference runtime, CLI, FPRM path, ECS R0 executable boundary, and structural-guidance composition. |
| `src/elpis_reference/structural_guidance/` | Validated-source structural-guidance composition and stage authority boundaries. |
| `src/elpis/` | Shared contracts/policies including the canonical Python AST and capability machinery. |
| `components/Pipeline/P0ControlProtocol/` | P0 control protocol, canonical relational Semantic IR, projection and validation mechanisms. |
| `components/TRMFractalSpine/` | Structural TRM contracts/refinement surfaces. |
| `components/DarwinianMatrix/` | Projector, clamp, search/refinement and related deterministic mechanisms. |
| `components/Grid81/` | Canonical Grid81 substrate, reader, state, and strict read-only boundary. |
| `components/Grid81StructuralSemantics/` | Grid81 structural semantic contracts. |
| `components/Grid81TypedProjectionCompiler/` | Typed Grid81 projection compiler. |
| `components/Grid81StructuralGroupProjectionCompiler/` | Structural group projection compiler. |
| `components/Grid81DeterministicStructuralAdjudicator/` | Deterministic structural adjudication. |
| `components/Grid81DeterministicCapabilityAuthorityEvaluator/` | Capability authority evaluation. |
| `components/Grid81DeterministicCapabilityConsumptionCompiler/` | Capability consumption compilation. |
| `components/Grid81DeterministicCapabilityApplicationExecutor/` | Capability application boundary. |
| `components/Grid81DeterministicCanonicalPromotionPlanner/` | Canonical promotion planning; not a qualified canonical-state writer. |
| `components/CNumPyCortex/` | Optional telemetry-first Grid81 transport/recursion component. |
| `components/FuryanLocusOracle/` | Frozen independent finite-placement oracle and certificate machinery. |
| `components/StreamingRegexIngress/` | Bounded native Regex lexical ingress. |
| `components/RegexHACFQueryIngress/` | Bounded Regex + HACF + query-local proposal composition. |
| `components/QueryLocalProposalIngress/` | Atomic query-local `PROPOSED_UNADMITTED` proposal overlay. |
| `native/hacf/` | Native HACF implementation. |
| `native/hacf_bridge/` | Native/Python HACF bridge. |
| `native/semantic-spine/` | Native Semantic Structural Spine. |
| `native/elpis-header/` | Header/runtime-side Grid81 observation integration. |
| `runtime/R0/` | Historical deterministic offline structural transaction integration. |
| `runtime/R1/` | Historical bounded HACF retrieval + R0 integration. |
| `ECS/ECS_AUTHORITY/STRUCTURAL_R0/` | Normative public ECS Structural Authority R0 contract. |
| `ECS/science/` | Closed Branch35–40 scientific evidence and adjudication lineage; evidence bytes remain authority-bound. |
| `tests/` | Mechanism, determinism, integration, mutation, adversarial, and release tests. |
| `manifests/` | Versioned release manifests and public component registry. |
| `docs/` | Architecture, build, qualification, provenance, and release-policy documentation. |
| `.github/` | Hosted qualification workflows. |
| `CHANGELOG.md` | Development/release chronology. |
| `RELEASE_NOTES/` | Release-specific claim and qualification boundaries. |

For current shipped-component truth, prefer `manifests/PUBLIC_COMPONENT_REGISTRY.json` over the broader internal canonical registry. For a component's detailed claim boundary, inspect its local README/manifest and corresponding tests rather than inferring capability from its name.

---

## 14. Reproducibility, falsification, and release integrity

Elpis treats qualification as an attempt to make claims easy to attack. A bounded claim should identify exact source/configuration/input authority, deterministic identities where claimed, intended negative branches, and independent checks where practical.

Representative falsifiers include:

- a forbidden transition succeeds;
- a negative mutation passes because the test swallowed its own assertion;
- equivalent canonical inputs produce different identities where determinism is claimed;
- a terminal artifact widens its own authority;
- a model proposal bypasses deterministic admission;
- generated source executes without a separately authorized execution boundary;
- an independent oracle disagrees with a production claim inside the oracle's qualified domain;
- an installed package only works because a source-tree path is injected;
- a release workflow validates an unrelated run instead of the exact target SHA/event; or
- release bytes no longer match the immutable manifest that claims to describe them.

Mechanical harness failure is classified separately from scientific/security/integrity non-pass. Frozen scientific or structural authority must not be rewritten merely to make a harness green.

### Published releases are immutable objects

A release identity is bound by `VERSION`, canonical declared release text, the exact Git tree, and a version-specific write-once release manifest. Published predecessor manifests remain immutable even when a public release candidate failed before tagging or GitHub Release registration.

Tracked changes after a sealed published release — including documentation-only changes — belong to a successor development/release identity. The historical manifest is not regenerated to describe new bytes.

From a pristine checkout of a sealed release object:

```bash
python tools/verify_public_release.py
python tools/ci_secret_scan.py .
```

Release qualification is intentionally staged: local qualification, release commit, public-main push and exact-SHA hosted CI, annotated tag and tag CI, GitHub Release/readback and release-event CI, and package-registry publication are separate gates unless an explicit release protocol states otherwise.

---

## 15. Licensing

Elpis source code is distributed under the [MIT License](LICENSE) unless an individual file or bundled third-party component states otherwise.

Third-party model, code, and data obligations are separate from the repository's own MIT-licensed source. Consult [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), `LICENSES/`, component-local notices, and model provenance records before redistributing bundled or downloaded third-party artifacts.

The license grants software-use rights; it does not expand the scientific claims, authority boundaries, qualification scope, or safety guarantees described here.
