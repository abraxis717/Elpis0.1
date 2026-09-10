# Elpis

**A deterministic structural-reasoning architecture for bounded learned proposals, explicit authority, and falsifiable runtime composition.**

## Abstract

Elpis investigates whether learned components can contribute useful structural proposals without implicitly acquiring authority over the representations, admissible state transitions, validation criteria, or execution boundaries that govern those proposals. The system separates typed semantic representation from deterministic projection, learned structural guidance from transition authority, source construction from execution, and evidence from reusable capability. Its present research surface combines a canonical semantic request graph, deterministic projection into an explicit 81-cell Grid81 control topology, bounded TRM guidance, authority-mediated materialization and planning, deterministic source construction, and static Python validation.

The current repository contains a qualified structural-guidance runtime and a separate public reference-model path. The structural-guidance path keeps the learned model behind an explicit default-OFF admission gate, fixes its authority at zero, and retains candidate legality and transition execution in deterministic code. The terminal validated-source composition binds the semantic input, topology, model checkpoint, materialization, planning artifact, decoder plan, source artifact, and validation evidence by deterministic identities while explicitly setting execution authority to false. Independent FuryanLocusOracle R0 qualification established a historical negative result for the earlier C2R6-P0 allocator. Elpis2.1.8 replaces that incomplete greedy strategy with deterministic joint rank/locus allocation for the audited subset while retaining Furyan as frozen independent evidence rather than runtime authority.

Elpis is therefore presented as a falsifiable systems-research program rather than a general intelligence claim. It does not claim solved alignment, general Grid81 satisfiability, arbitrary autonomous execution, general semantic correctness, cross-process attestation, autonomous implementation synthesis, AGI, or ASI. The intended standard is narrower: each mechanism should state the authority it possesses, the evidence that qualifies it, the conditions under which it fails, and the observations that would falsify the claim being made.

### Elpis2.1.13

**Release line: Elpis2.1.13**

Elpis2.1.13 makes the published ECS Structural Authority R0 contract executable
and hardens repository, packaging, containment, and CI integrity.

The bounded E0R2 diagnostic terminates `SEMANTIC_IR_INSUFFICIENT`: the existing
Semantic IR and Projector preserve participation facts descriptively but do not
provide the writable whole-column participation primitive required by the
published mutation contract. One executable semantic primitive remains
unresolved; E1 and E2 were not executed.

The release also reconciles canonical-only versus publicly shipped component
metadata, qualifies the installed Python assembly without source-tree
`PYTHONPATH` compensation, hardens canonical-root containment and private-path
scanning, and gates repository/tooling completeness.

No learned, Darwinian, or scientific execution is introduced.

## 1. Research Question and Scope

The central question is:

> **Can a learned component contribute useful structural search or ordering information while a deterministic substrate retains ownership of representation, admissibility, authority, validation, and terminal action?**

Elpis treats this as a systems question rather than as a claim about the internal reliability of a learned model. The relevant object is not only a model output, but the composition in which that output is produced, bounded, admitted, transformed, validated, and either accepted or rejected.

Let $x$ denote a typed semantic request, $S$ the current structural state, $M$ a learned proposer, $p=M(x,S)$ a proposal, and $J$ a deterministic adjudicator under an explicit contract $C$. The intended separation is:

$$
p = M(x,S), \qquad S' = J(x,S,p;C),
$$

with $M$ unable to redefine $C$, widen its own writable scope, grant itself a capability, or convert confidence into permission. A learned proposal may influence the search order or candidate selection within an already admitted space; it is not itself the authority that makes the transition legal.

The current repository scope is correspondingly bounded. It includes qualified mechanisms for semantic representation, structural projection, bounded learned guidance, authority-mediated downstream transformations, validated-source construction, a public Sudoku reference-model path, independent finite-placement science, and release-integrity enforcement. It does not include a trusted natural-language-to-semantic compiler, unrestricted autonomous code synthesis, generated-source execution, persistent cross-process authority, or a general-purpose autonomous agent runtime.

The term **authority** is used operationally: the explicit capability to admit, reveal, consume, mutate, validate, execute, or otherwise advance a state transition. It is not used as a synonym for model confidence, heuristic usefulness, or semantic plausibility.

---

## 2. Architectural Principle: Proposal Without Authority

Many model-centric agent architectures allow a single learned system to interpret an instruction, choose a representation, plan, call tools, validate its own output, and act. Elpis deliberately decomposes those roles. The learned component is treated as a bounded proposer inside a substrate whose contracts and authority are external to the model.

The principle can be summarized as four separations:

1. **Representation is not proposal.** The semantic request and structural topology are defined independently of the learned proposal that may refine them.
2. **Proposal is not admissibility.** A candidate produced by a model is not accepted merely because the model produced it.
3. **Validation is not execution.** A source artifact may pass a static policy while retaining zero execution authority.
4. **Evidence is not capability.** A receipt or terminal result can prove what occurred without becoming reusable permission to perform another transition.

In the qualified structural-guidance component, the request-level gate defaults **OFF**. The semantic binding envelope remains outside the model input. TRM authority is always zero. Candidate legality and transition execution remain owned by deterministic C2R6-P1 machinery. The frozen TRM0 may alter stable ordering before a strict-improvement scan and can therefore affect which action is selected only among equal-best improving candidates; plateau escape remains unguided. If guidance cannot be admitted, the component returns `FALLBACK_REQUIRED` rather than silently executing an alternate path.

This is the primary distinction between Elpis and a generic LLM agent framework. The research object is not an LLM with a larger tool surface. It is a composition in which tool access, writable state, transition legality, source validation, and execution authority are separately represented and can be independently tested.

This separation is intended to make failure easier to localize. It is **not** a proof that bounded authority solves alignment or that a sufficiently complex composition cannot fail in other ways.

---

## 3. System Architecture

At the current qualified boundary, the structural path is organized around an explicit semantic object, a deterministic control topology, bounded learned guidance, and a sequence of authority-mediated transformations.

```text
P0SemanticRequestV1
        |
        v
Deterministic Projector
        |
        v
Grid81 structural state
        |
        v
bounded TRM guidance
        |
        v
deterministic transition validation / replay
        |
        v
ResolvedStructuralTopologyV1
        |
        v
materialization -> planning -> decoding
        |
        v
deterministic source construction
        |
        v
canonical Python AST policy
        |
        v
StructuralGuidanceRuntimeResultV1
        |
        +-- authority_granted      = 0
        +-- validation_authorized  = false
        +-- execution_authorized   = false
```

### 3.1 Semantic request

`P0SemanticRequestV1` is a canonical relational task representation independent of Grid81. The contract represents:

- entities;
- operations;
- constraints;
- relations;
- dependencies;
- quantities; and
- declared output entities.

The semantic layer has canonical identifiers, validation rules, canonical serialization, and digest-bound identity. It does **not** parse natural language, and it does not itself allocate semantic objects into Grid81. Natural-language compilation therefore remains outside the qualified semantic contract.

This distinction prevents an upstream language model from silently defining both the problem representation and the structural state into which it will later propose changes.

### 3.2 Grid81

Grid81 is the explicit bounded structural control space used by the current P0 projection path. It is an 81-cell topology organized as nine ranks across nine lanes, with explicit cell contents, lane bindings, invariants, frozen and writable masks, residual state, semantic sidecar bindings, and a structural input fingerprint.

The C2R6-P0 Projector is a pure function of an explicit projection input and a pinned ruleset. Its implementation does not read the filesystem, environment, network, wall clock, or a learned model. It canonicalizes the semantic graph, analyzes scheduling structure, performs bounded capacity checks, allocates lanes/ranks/loci, constructs masks and invariants, derives residual state, and emits a replay trace and projection digest.

Expected rejections are represented as typed results rather than by opportunistic fallback. Capacity failure may produce `DECOMPOSITION_REQUIRED`; structural contradictions and invalid inputs are distinct conditions. Importantly, `DECOMPOSITION_REQUIRED` is an allocator outcome, not a proof that the corresponding semantic structure is globally unsatisfiable in Grid81.

Grid81 is an experimental structural substrate. Elpis does not claim that an 81-cell representation is universal or that intelligence is fundamentally geometric.

### 3.3 Structural guidance

The qualified learned component is a frozen structural TRM guidance path. Its role is deliberately narrow:

- request-level admission is explicit and defaults OFF;
- the admissible checkpoint SHA-256 is hard-pinned while the host supplies the checkpoint path;
- the semantic binding envelope remains outside model input;
- the model receives no transition authority;
- deterministic candidate legality remains external to the model;
- TRM0 can affect stable ordering only among equal-best improving candidates before the strict-improvement scan;
- plateau escape is not model-guided; and
- failed guidance returns explicit fallback control to the enclosing controller.

The model is therefore a proposer/refiner within a fixed structural contract. It is not the authority root and it cannot redefine the writable topology merely by producing an output.

### 3.4 Authority and validation

Elpis models sensitive downstream transitions as explicit authority boundaries rather than ambient permissions. The validated-source composition uses one-shot authority objects for materialization, planning, decoding, source emission, and validation. Each stage consumes a specific bound transition rather than inheriting unrestricted authority from the previous stage.

The resulting lineage binds, among other identities:

```text
semantic input
    -> topology
    -> checkpoint
    -> materialization
    -> planning input
    -> planning artifact
    -> decoder plan
    -> source input
    -> source artifact
    -> validation evidence
    -> terminal runtime result
```

Terminal structural results are authority-zero. Validation evidence does not propagate planning, decoding, source-emission, validation, or execution authority.

Separately, the process-local `CapabilityRegistry` uses explicitly scoped capability issuance and digest-bound receipts. Receipt verification is intentionally bounded to the active process/issuer context; no cross-process or asymmetric attestation claim is made.

### 3.5 Validated-source runtime

The terminal structural-guidance runtime composes already-qualified stages through static source validation. It can produce a deterministic source artifact and a terminal validation decision, but it does not compile, import, invoke, or execute generated source.

The canonical Python AST policy distinguishes syntax, entrypoint, import, scope-mutation, banned-call, and valid-policy outcomes. Elpis2.1.8 retains the earlier bypass hardening, makes canonical restrictions non-subtractive, and rejects the qualified frame, generator, coroutine, async-generator, traceback, and code-object introspection families.

The closure policy requires Python source that parses and contains the named
function entrypoint. Imports, global/nonlocal declarations, indirect calls,
recovered method values, unknown attributes, decorators, all class definitions,
`with` and `async with` are rejected. Builtin names loaded as values are rejected
except in an admitted direct-call position or as an expressly approved raised
exception. Raised expressions must be an approved exception name or its direct
constructor call: `ValueError`, `TypeError`, `IndexError`, `KeyError`,
`RuntimeError`, or `Exception`. Bare re-raise remains admitted. `BaseException`,
`SystemExit`, `KeyboardInterrupt`, `GeneratorExit`, and other raised names are
rejected. Canonical bans remain non-subtractive.

Direct named calls are limited to source-defined functions and:
`abs all any bool dict divmod enumerate filter float frozenset int isinstance
issubclass iter len list map max min next pow range reversed round set slice
sorted str sum tuple zip chr ord bin hex oct repr`, plus the six approved
exception constructors. Direct attribute calls are limited to:
`append extend insert pop remove clear copy count index reverse sort get keys
values items setdefault update add discard union intersection difference strip
lstrip rstrip split rsplit splitlines join replace lower upper casefold startswith
endswith find rfind isdigit isalpha isalnum isspace`.

Other parsed AST forms pass these filters when they contain no prohibited child.
This remains an exclusion policy, **not a fully closed admitted grammar**.
Undecorated async functions, `await`, async iteration, generators and
`yield`/`yield from` have no resolved synchronous-language contract here; full
P0.5 closure is blocked on that disposition. Ordinary data loops, comprehensions,
lambdas used as data-operation callbacks, and calls between defined functions
remain regression-covered. Static acceptance still grants no execution authority.


A result of:

```text
validation_code = AST_VALID
```

means that the artifact parsed and passed the configured static P0 policy. It does **not** mean that the program is functionally correct, safe under arbitrary execution, semantically faithful to the task, or authorized to run.

---

## 4. Qualified Capabilities

The table below states the current public claim surface. “Qualified” means that the repository contains a frozen implementation and qualification boundary for the stated mechanism; it does not widen the claim beyond that mechanism.

| Capability | Qualified claim | Boundary |
|---|---|---|
| Canonical semantic request | Typed relational requests can be validated, canonicalized, and digest-bound. | No trusted natural-language parsing claim. |
| Semantic → Grid81 projection | Supported semantic structure is deterministically projected under a pinned ruleset with typed rejections and replay evidence. | No universal allocation-completeness claim. |
| Structural TRM guidance | A frozen checkpoint can influence bounded equal-best ordering when explicitly admitted. | Gate defaults OFF; TRM authority remains zero. |
| Resolved topology | Admitted guidance can be transformed into a digest-bound resolved structural topology while preserving authority-zero semantics. | Requires a real admitted guidance result. |
| Materialization and planning | Resolved topology can pass through explicit one-shot materialization and deterministic planning contracts. | Authority is stage-bound rather than ambient. |
| Decoder/source construction | Authority-zero planning artifacts can be normalized into deterministic decoder/source artifacts. | Source construction is not execution. |
| Static Python validation | Generated Python can be checked against the canonical P0 AST policy, including non-subtractive canonical restrictions and the qualified introspection-family closures. | Static policy validity is not functional correctness or sandboxing. |
| Terminal runtime result | The validated-source runtime emits digest-bound terminal results with zero authority and no execution permission. | No generated-source execution occurs. |
| FuryanLocusOracle R0 | A finite, independently qualified rank/locus oracle can decide the admitted R0 placement model and emit independently checkable SAT certificates. | Not a general Grid81 solver and not production runtime authority. |
| Public FPRM reference path | A pinned public FPRM checkpoint can be fetched, verified, strictly loaded, and used for real CPU Sudoku inference. | Sudoku capability is evidence only for the Sudoku reference task. |
| Release integrity | Release identity, declared text, manifests, secret/private-path scanning, and intended negative mutations are fail-closed and version-bound. | A development branch is not itself a sealed release. |

The qualified claim surface intentionally includes negative evidence. A component is not promoted to a stronger claim merely because a neighboring stage is green.

---

## 5. Known Limitations and Negative Results

### 5.1 Historical allocator incompleteness and current repair

FuryanLocusOracle R0 remains the frozen production-independent finite
placement oracle that established the historical C2R6-P0 completeness defect
for the bounded audited `ROUTE`/`state_feeds` subset.

The frozen result, including representative counterexamples, the 44,005-case
canonical core, independently checked certificates, 12/12 mutation kills, and
fresh-process identity evidence, remains unchanged.

Elpis2.1.8 repairs the corresponding production strategy by jointly assigning
operation ranks and auxiliary loci rather than committing to the earlier
greedy schedule before auxiliary feasibility is known. Current-production
successor tests compare the allocator against Furyan over all 44,005 canonical
core cases and retain separate stress/tail and fresh-process checks.

This qualification remains bounded to the admitted finite model. It does not
establish general Grid81 satisfiability or promote Furyan into runtime
authority.

The closure successor imposes a deterministic search-entry budget through
`c2r6p0.ruleset.v2` and records it in `c2r6p0.projection-trace.v2`. The default is
84 entries (4 × the measured maximum of 21 over the predeclared 44,202-case
corpus), with an explicit maximum configurable budget of 4,096. A cutoff returns
`SEARCH_BUDGET_EXHAUSTED`, independently of UNSAT or decomposition. Admission
propagates that status through a typed exception carrying the projection and
trace. This is an operational bound, not a completeness theorem.


### 5.2 Static validity without functional correctness

A separate validated-source experiment supplied the runtime with a typed `merge_intervals` semantic representation, the natural-language task, the frozen structural TRM0, and the full validated-source composition, but no correct implementation body.

The blind result was:

```text
runtime_status      = VALIDATED_SOURCE
validation_code     = AST_VALID
functional_pass     = false
functional_failures = 7 / 7
```

The emitted function contained `return None`. A positive-control arm using the same semantic input and resolved topology but a known-correct implementation body passed the downstream source and functional-validation path.

This negative result localizes the present boundary: semantic representation, structural projection, learned guidance, resolved topology, materialization, planning transport, decoder normalization, source emission, and static validation can all function while autonomous implementation synthesis still fails.

### 5.3 Process-local receipt verification

Receipt verification is process-local. The current mechanism does not claim cross-process persistence, asymmetric attestation, or globally reusable capability proofs. Bounded receipt retention is also an explicit implementation constraint rather than an unbounded audit log.

### Grid81 publication and consumption limits

The repository supplies a canonical-state reader and historical frozen state;
it contains no qualified writer for `HEAD.json` or generations. Durable
canonical-state mutation, atomic publication, and cross-process replay rejection
are outside its qualified boundary. A stored declaration of these properties is
not independent publication evidence.

Grid81 capability nonce digests identify deterministic bound inputs; they do not
establish one-time consumption. `ApplicationLedger` proves process-local
consumption only within the same in-memory ledger instance. The frozen
`.authority_audit.json` was produced by a constant generator and is not independent
proof of its claimed properties. See [Grid81's boundary](components/Grid81/README.md).

### 5.4 Semantic replay identity and process-local security identity

Elpis2.1.8 separates deterministic semantic/replay identity from ephemeral
authority and capability-instance evidence.

For equal deterministic semantic inputs, replay-facing identity can therefore
remain stable across fresh processes without making security nonces,
capabilities, authority instances, or consumption evidence deterministic.

Security authority remains process-local. This repair does not establish
cross-process bearer capability, asymmetric attestation, or external trust.

### 5.5 Explicit non-claims

Elpis currently makes no claim of:

- trusted natural-language → semantic-graph compilation;
- general autonomous implementation synthesis;
- generated-source execution authority;
- arbitrary autonomous tool execution;
- general Grid81 satisfiability;
- universal allocator completeness;
- cross-process or asymmetric receipt attestation;
- unrestricted learned-model authority;
- generalized held-out competence unless separately qualified;
- solved alignment;
- AGI or ASI; or
- performance improvement not demonstrated by qualification.

These are not rhetorical disclaimers attached after the fact; they delimit the current research object.

---

## 6. Current Runtime Composition

The qualified validated-source composition is implemented under `src/elpis_reference/structural_guidance/`. The runtime module states the composition explicitly:

```text
Semantic IR
    -> Projector
    -> bounded structural-guidance admission
    -> resolved topology
    -> zero-authority observation
    -> one-shot structural materialization
    -> planning input
    -> one-shot planning
    -> deterministic structural planning
    -> one-shot decoding adapter
    -> authority-zero decoder-specific plan
    -> prompt/source-input binding
    -> one-shot source emission
    -> deterministic source emission
    -> one-shot validation
    -> canonical Python AST policy
    -> authority-zero terminal validation result
```

The corresponding public terminal object is `StructuralGuidanceRuntimeResultV1`. Its identity covers the major intermediate digests and the exact emitted source SHA-256. Validation enforces:

```text
authority_granted     == 0
validation_authorized == false
execution_authorized  == false
```

The runtime refuses disabled structural-guidance configuration when the validated-source path requires a real admitted result. Validation rejection is terminal and authority-zero. No generated source executes in either terminal state.

At the broader architectural level, an external orchestrator such as Prime is intended to remain a thin control plane rather than the owner of Grid81, semantic admission, structural resolution, or execution authority. The learned TRM is similarly a bounded proposer rather than the authority root. That broader composition is an architectural direction; only repository-qualified stages should be treated as shipped claims.

---

## 7. Reproducibility and Falsification

Elpis treats reproducibility as an attempt to make claims easy to attack. A qualification should bind exact source, exact configuration, exact inputs, deterministic identities where claimed, intended negative branches, and independent checks where practical.

### Release integrity

From a pristine checkout of the published release object:

```bash
python tools/verify_public_release.py
python tools/ci_secret_scan.py .
```

The public verifier checks release identity and manifest consistency, including the canonical declared release text. Elpis2.1.6 adds negative mutations proving that stale README or canonical release-note declarations were accepted by the old verifier and rejected by the repaired one for the intended reason.

### Structural runtime

The repository exposes focused tests for the validated-source composition:

```bash
export PYTHONPATH="$PWD/src:$PWD/components:$PWD/components/Pipeline/P0ControlProtocol/src:$PWD/components/TRMFractalSpine/src"

python -m pytest -q \
  tests/test_python_ast_policy_convergence.py \
  tests/test_structural_guidance_structural_validator.py \
  tests/test_structural_guidance_validated_source_runtime.py \
  tests/test_structural_guidance_runtime_admission.py
```

These tests exercise policy convergence, explicit guidance admission, terminal digest integrity, authority-zero results, validation rejection, source tamper detection, and the prohibition on generated-source execution.

### Furyan release integration

The public release includes a frozen-source integration gate for Furyan:

```bash
python -m pytest -q tests/test_furyan_release_integration.py
```

The full scientific qualification was performed against its frozen science authority and should not be reconstructed casually from the release branch. The release integration test instead verifies that the exact qualified scientific bytes were carried into the public release unchanged.

### Falsification criteria

The project treats the following as evidence against a claimed mechanism rather than as cosmetic test failures:

- a forbidden transition succeeds;
- a negative mutation fails to fire for its intended reason;
- equivalent canonical inputs produce different identities where determinism is claimed;
- a terminal artifact can widen its own authority;
- a model proposal bypasses deterministic admission;
- generated source is executed without a separately authorized execution boundary;
- an independent oracle disagrees with a production claim inside the oracle's qualified domain; or
- release bytes no longer match the immutable manifest that claims to describe them.

A mechanical harness failure is classified separately from a scientific/security/integrity non-pass. Frozen evidence should not be rewritten merely to make a harness green.

---

## 8. Reference Model

Elpis contains a public reference-model path separate from the structural TRM research path. The reference path exists to provide a reproducible example of real pinned model loading and inference rather than to stand in for the complete Elpis architecture.

The PyPI project name `elpis` is currently owned by an unrelated automatic-speech-recognition project. Do **not** use `pip install elpis` to obtain this repository.

From a pristine source checkout:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[trm]"
```

Fetch and verify the pinned public model:

```bash
elpis model fetch
elpis model verify
```

Run real CPU Sudoku inference:

```bash
elpis sudoku solve \
  --puzzle '.34678912672195348198342567859761423426853791713924856961537284287419635345286179' \
  --device cpu
```

The reference runtime verifies the pinned model identity and state ABI before loading. This path demonstrates a reproducible model-integrity and inference mechanism.

It does not establish generalized reasoning. **Sudoku capability is evidence of Sudoku capability.** The public FPRM reference path and the frozen structural TRM path should not be conflated.

---

## 9. Repository Organization

The repository is organized so that architectural surfaces, qualified components, tests, evidence, and release authority can be inspected independently.

| Path | Role |
|---|---|
| `src/elpis_reference/` | Portable public runtime and reference-model path. |
| `src/elpis_reference/structural_guidance/` | End-to-end validated-source structural-guidance composition and its authority boundaries. |
| `src/elpis/` | Shared contracts and policies, including the canonical Python AST policy and capability machinery. |
| `components/Grid81/` | Canonical Grid81 substrate artifacts. |
| `components/TRMFractalSpine/` | Structural TRM contracts and refinement surfaces. |
| `components/DarwinianMatrix/` | Structural clamp, Projector, search/refinement research, and related deterministic mechanisms. |
| `components/Pipeline/P0ControlProtocol/` | P0 control-protocol and validation mechanisms. |
| `components/FuryanLocusOracle/` | Frozen independent finite-placement oracle, specification, certificate validation, and release-integrated scientific source. |
| `tests/` | Mechanism, negative, determinism, integration, mutation, and red-team tests. |
| `manifests/` | Versioned release manifests and immutable release-integrity authority. |
| `docs/` | Architecture, build, qualification, and provenance documentation. |
| `.github/` | Hosted qualification workflows. |
| `CHANGELOG.md` | Historical development chronology. |
| `RELEASE_NOTES_*.md` | Release-specific claim and qualification boundaries. |

For the current structural architecture, start with `src/elpis_reference/structural_guidance/README.md` and `runtime.py`, then inspect the corresponding tests. For Grid81 placement semantics, follow the P0 Projector authority and Furyan's separately bounded specification rather than inferring semantics from component names alone.

---

## 10. Research Frontier

The current frontier is defined by unresolved mechanisms, not by a target level of anthropomorphic autonomy.

### Allocator completeness

The highest-priority scientific engineering target is a C2R6-P0 allocator repair that removes the qualified incompleteness without special-casing the discovered counterexample. A satisfactory repair should use a complete joint rank/locus allocation formulation, preserve deterministic canonical output, distinguish true capacity exhaustion from algorithmic failure, and differentially qualify the supported subset against the frozen Furyan authority.

### Direct typed end-to-end composition

The direct control path should be closed before introducing broader search/evolution layers. The outstanding cross-process identity blocker should be repaired by separating deterministic semantic/replay identity from ephemeral capability-instance identity, not by weakening security identity.

### Semantic compilation and source synthesis

Trusted natural-language → semantic compilation remains open. Autonomous implementation synthesis also remains open: current evidence shows that a pipeline can produce AST-valid source while failing every functional test. Future synthesis claims therefore require independent functional validation rather than source-policy validity alone.

### Authority and receipt evolution

Future work may include persistent or asymmetric receipt verification, improved bounded-retention behavior, and clearer separation between evidence identity and live capability identity. These should be separate tranches because they change authority semantics.

### Runtime dependency reduction

The current package has a hard `torch` dependency. Some deterministic R0 verdict paths may not require that dependency for their own arithmetic. Any reduction should be treated as a separate compatibility/qualification tranche rather than incidental cleanup.

### Darwinian refinement

DarwinianMatrix-style refinement remains a secondary research path. The architectural order is direct typed composition first, optional bounded evolutionary/refinement search later. Adding a search layer must not move Grid81 ownership, semantic admission, or execution authority into the orchestrator or learned model.

---

## 11. Release Integrity and Provenance

Elpis treats a published release as an immutable object rather than a moving branch label.

A release identity is bound by repository `VERSION`, canonical declared release text, the exact Git tree, and a version-specific manifest. The sealer is write-once for published manifest identities. Once a version is sealed and published, tracked changes — including documentation-only changes — require a successor release identity or an explicitly unsealed development branch; the previous manifest is not regenerated to describe new bytes.

Elpis2.1.6 specifically adds grammar-bound declared-text verification for:

```text
README.md:
**Release line: ElpisX.Y.Z**

RELEASE_NOTES.md:
## Version: vX.Y.Z
```

The verifier rejects missing, duplicate, ambiguous, or mismatched canonical declarations. A random occurrence of the current version elsewhere in the document cannot satisfy the guard.

The release-integrity model is intentionally adversarial. Negative mutations must demonstrate that a forbidden state is rejected for the intended reason, and the corresponding pre-fix control must establish that the unpatched guard would have accepted the mutation where that claim is made.

For Elpis2.1.6, the immutable release object is:

```text
commit       e0c5462b81525fe45e2f5342dfc2a227b9e6f7f2
tree         75ae3ab9d203c3d030bfc0c3bd22717300d9fd03
manifest     manifests/Elpis2.1.6.RELEASE_MANIFEST.json
manifest sha eae0b7b5acb5ab54d06396c4002f300e3051a4d636b9b86a1a4e26157c126ce6
```

The repository should be read as a hierarchy of claims: source defines a mechanism, tests attack that mechanism, qualification binds an exact object, and release manifests bind the published bytes. None of those layers should silently substitute for another.

---

## 12. Licensing

Elpis source code is distributed under the [MIT License](LICENSE) unless an individual file or bundled third-party component states otherwise.

Third-party model, code, and data obligations are separate from the repository's own MIT-licensed source. Consult [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), `LICENSES/`, component-local notices, and model provenance records before redistributing bundled or downloaded third-party artifacts.

The license grants software-use rights; it does not expand the scientific claims, authority boundaries, qualification scope, or safety guarantees described in this paper-style README.
