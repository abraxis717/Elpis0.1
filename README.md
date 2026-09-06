# Elpis

> **Structural reasoning without giving the learned model the keys.**

**Release line: Elpis2.1.6**
Deterministic structural AI research with explicit topology, bounded learned proposals, digest-bound authority, and falsifiable runtime claims.

Elpis is an experiment in a simple architectural idea:

**learned systems should be allowed to propose — without silently owning the state, rules, validation, or execution authority around those proposals.**

The project combines a typed semantic graph, deterministic projection into Grid81, learned structural guidance, explicit authority transitions, deterministic materialization, source construction, and static validation. A separate public reference path runs a real pinned FPRM model on Sudoku.

Elpis is **not** presented as a solved alignment system, an AGI, or an autonomous coding agent. The repository is deliberately organized so that working mechanisms, negative results, and unfinished research remain distinguishable and testable.

---

## If you only read one section

Elpis separates **reasoning** from **authority**.

```text
semantic request
      |
      v
deterministic projection
      |
      v
Grid81 structural topology
      |
      v
learned proposal / refinement
      |
      v
deterministic adjudication
      |
      v
bounded downstream capabilities
```

The learned model does not get to redefine the topology it is modifying, widen its own writable scope, grant itself execution authority, or turn confidence into permission.

That separation is the research surface.

---

## What works today

### Qualified and working

- **Release integrity** — VERSION-driven manifest verification, negative mutation tests, fail-closed release guards.
- **Typed semantic requests** — canonical relational task representation with digest-bound identity.
- **Deterministic semantic → Grid81 projection** — explicit masks, bindings, invariants, residuals, and rejection states.
- **Frozen structural TRM guidance** — works when the qualified checkpoint is explicitly supplied; admission remains opt-in.
- **Resolved structural topology and materialization** — bounded downstream contracts with explicit authority transitions.
- **Validated-source runtime** — deterministic source construction and static validation without execution authority.
- **Canonical Python AST policy** — rejects malformed syntax, imports, scope mutation, direct banned calls, references to configured banned call names, selected dynamic built-in escape hatches, and dunder-attribute introspection; this is a static policy boundary, not an execution sandbox.
- **Public FPRM reference model** — pinned model bootstrap, verification, strict load, and real CPU Sudoku inference.
- **FuryanLocusOracle R0** — independently qualified finite rank/locus satisfiability oracle with certificate validation, exhaustive reference cross-checking, mutation qualification, and deterministic result identity.
- **Bounded feedback / RELEASE machinery** — failures can release pre-existing structural support without granting arbitrary authority to invent new structure.

### Real, but deliberately limited

- Structural TRM guidance is **not enabled by default**.
- The structural TRM checkpoint is qualified, but does **not yet** have the same public bootstrap path as the FPRM Sudoku model.
- The current C2R6-P0 structural-guidance allocator is known to be incomplete for a qualified ROUTE/`state_feeds` subset: it can request decomposition where a one-Grid81 placement exists. Elpis2.1.5 introduced the independent oracle and regression evidence; the allocator remains unrepaired in Elpis2.1.6.
- Receipt verification remains **process-local**; no cross-process or asymmetric attestation claim is made.
- Static AST validity means **policy-valid source**, not functional correctness.

### Not implemented yet

- Trusted natural-language → semantic graph compilation.
- General autonomous implementation synthesis.
- Generated-source execution.
- Persistent cross-process authority.
- A general-purpose autonomous agent runtime.

That distinction matters. A working mechanism is not silently promoted into a larger intelligence or alignment claim.

---

## Try the real reference path

The PyPI project name `elpis` is currently owned by an unrelated automatic-speech-recognition project. **Do not use `pip install elpis` for this repository.**

Start from a pristine source checkout of the release:

```bash
python tools/verify_public_release.py
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
```

Fetch and verify the pinned public model:

```bash
elpis model fetch
elpis model verify
```

Run a real CPU inference:

```bash
elpis sudoku solve \
  --puzzle '.34678912672195348198342567859761423426853791713924856961537284287419635345286179' \
  --device cpu
```

The model is loaded only after its pinned identity and state ABI are verified.

The Sudoku path is intentionally narrow: **Sudoku capability is evidence of Sudoku capability, not evidence of general reasoning.**

---

## Why separate proposal from authority?

Many learned systems collapse several roles into one model:

```text
interpretation
representation
planning
proposal
validation
action
```

Elpis tries to pull those roles apart.

A learned component may propose a structural change without owning the rules that define the structure. A decoder may construct candidate source without acquiring permission to execute it. A validator may reject an artifact without gaining authority to repair arbitrary state. A terminal result may carry evidence without becoming a reusable capability.

In practice, Elpis repeatedly asks:

> **What is the smallest amount of authority this learned component actually needs?**

The hypothesis is modest: if learned components hold less authority, failures may become easier to contain, reproduce, inspect, and falsify.

That is an architectural hypothesis, not a proof that bounded authority solves alignment.

---

## The structural substrate: Grid81

Elpis uses **Grid81** as a bounded structural control space.

It is an 81-cell topology with explicit lanes, ranks, masks, bindings, invariants, residuals, and transition rules. A typed semantic request can describe entities, operations, dependencies, relations, constraints, quantities, and outputs; the deterministic Projector maps supported structure into Grid81.

```text
typed semantic graph
        |
        v
 deterministic Projector
        |
        v
+-----------------------+
|        Grid81         |
| masks / invariants    |
| bindings / residuals  |
| explicit write scope  |
+-----------------------+
        |
        v
 learned structural proposal
```

The learned model operates **inside** the admitted topology. It does not silently define that topology for itself.

Grid81 is an experimental substrate, not a claim that intelligence is fundamentally geometric or that one 81-cell representation is universal.

---

## Current runtime path

The qualified validated-source composition is approximately:

```text
P0SemanticRequestV1
        |
        v
Projector
        |
        v
structural guidance
        |
        v
ResolvedStructuralTopologyV1
        |
        v
ResolvedStructuralMaterializationV1
        |
        v
PlanningInputV1
        |
        v
StructuralPlanningArtifactV1
        |
        v
DecoderSpecificPlanV1
        |
        v
DecoderSourceInputV1
        |
        v
DecodedSourceArtifactV1
        |
        v
StructuralValidationEvidenceV1
        |
        v
StructuralGuidanceRuntimeResultV1
```

Terminal structural results retain the authority boundary:

```text
authority_granted = 0
validation_authorized = false
execution_authorized = false
```

The runtime may produce validated source. It does **not** compile, import, invoke, or execute generated source.

---

## Elpis2.1.4 release-integrity repair

Elpis2.1.4 is a **mechanical release-integrity successor** to Elpis2.1.3. It preserves the 2.1.3 runtime and authority semantics while repairing the write-once sealing boundary and binding this README into the successor manifest.

Elpis2.1.3 introduced the fail-closed authority and release-qualification hardening summarized below.

The most important breaking change is intentional:

```python
CapabilityRegistry.issue(scope=...)
```

now requires a **non-empty explicit scope**. The previous empty default could behave as effectively unbounded authority. Scope binding is now fail-closed, and receipts sign the issue-time bound scope rather than a caller-supplied widening.

The release also hardens:

- process-local receipt verification by recomputing HMAC under the active issuer key;
- bounded receipt-retention windows and transactionally inert rejection paths;
- R0/R1 dependency containment and missing-evidence handling;
- release manifest identity selection from `VERSION`;
- mutation-tested secret/private-path scanning;
- dirty-tree and ephemeral-artifact rejection;
- strict UTF-8 scanning for declared text.

Pre-seal qualification recorded in the release notes includes:

```text
release mutations       20 / 20
authority focused       21 / 21
runtime guards          22 / 22
sealer / identity       10 / 10
full Python suite      313 / 313
Grid81                 122 / 122
R0                       26 / 26
native HACF              21 / 21
R1 positive              PASS
R1 required negatives    PASS
```

No performance claim is made by this release.

See [`RELEASE_NOTES_Elpis2.1.4.md`](RELEASE_NOTES_Elpis2.1.4.md) for the release-integrity repair and [`RELEASE_NOTES_Elpis2.1.3.md`](RELEASE_NOTES_Elpis2.1.3.md) for the inherited authority-hardening details.

---

## The useful failure

One of the most informative Elpis tests is a failure.

The system was given a typed semantic representation of `merge_intervals`, the natural-language task, the real frozen structural TRM0, and the complete validated-source runtime. No implementation body was supplied.

The blind result was:

```text
runtime_status      = VALIDATED_SOURCE
validation_code     = AST_VALID
functional_pass     = false
functional_failures = 7 / 7
```

The emitted function contained `return None`.

A positive-control arm used the same semantic input and resolved topology but supplied a known-correct body; the downstream source and functional-validation path passed.

That localizes the current boundary:

```text
semantic representation               working
deterministic projection               working
learned structural guidance            working
resolved topology                      working
materialization                        working
planning transport                     working
decoder normalization                  working
source emission                        working
static validation                      working
autonomous implementation synthesis    not working
```

This result is not hidden behind the successful AST check. It tells us where the actual research frontier is.

---

## Reproduce and falsify

Elpis is intended to be easier to disprove than to market.

### Release integrity

Run from a pristine checkout before installing or building inside the tree:

```bash
python tools/verify_public_release.py
python tools/ci_secret_scan.py .
```

The release verifier rejects inconsistent identities, undeclared files, malformed release authority, ephemeral build/cache content, and non-UTF-8 declared text.

### Model integrity

```bash
elpis model fetch
elpis model verify
```

A modified or ABI-incompatible checkpoint should fail verification.

### Structural runtime

From the repository root:

```bash
export PYTHONPATH="$PWD/src:$PWD/components:$PWD/components/Pipeline/P0ControlProtocol/src:$PWD/components/TRMFractalSpine/src"

python -m pytest -q \
  tests/test_python_ast_policy_convergence.py \
  tests/test_structural_guidance_structural_validator.py \
  tests/test_structural_guidance_validated_source_runtime.py \
  tests/test_structural_guidance_runtime_admission.py
```

These tests cover static-policy convergence, terminal digest integrity, explicit guidance admission, authority-zero results, validation rejection, source tamper detection, and the prohibition on generated-source execution.

Broader mechanism, determinism, integration, mutation, and red-team tests live under `tests/`.

---

## Repository map

You do not need to read the entire repository to understand the current system.

| Start here | What lives there |
|---|---|
| `src/elpis_reference/` | Portable runtime and public model path |
| `src/elpis_reference/structural_guidance/` | End-to-end structural-guidance composition |
| `src/elpis/` | Shared policies, authority, and contracts |
| `components/TRMFractalSpine/` | Structural TRM contracts and oracle/refinement surfaces |
| `components/DarwinianMatrix/` | Structural clamp and Projector authority machinery |
| `components/Pipeline/P0ControlProtocol/` | P0 control and validator mechanisms |
| `tests/` | Direct, negative, determinism, integration, mutation, and red-team tests |
| `manifests/` | Release and distribution integrity records |
| `docs/` | Build, testing, architecture, and provenance detail |
| `CHANGELOG.md` | Historical development and release chronology |

For architecture, start with `src/elpis_reference/structural_guidance/`. For truth, follow it immediately with the tests that exercise the component you care about.

---

## What is being built next

The immediate frontier is not “make the model more autonomous.” It is **close the direct typed transaction seam without widening authority**.

The intended direct path is:

```text
Prime / external orchestrator
        |
        v
typed Elpis request
        |
        v
P0 + canonical structural state
        |
        v
learned TRM proposal
        |
        v
deterministic adjudication
        |
        v
Projector RELEASE boundary
        |
        v
typed result + deterministic receipt
```

DarwinianMatrix search is deliberately deferred until the direct path is proven and replayable.

Other active research directions include:

- autonomous structural source synthesis;
- trustworthy natural-language semantic compilation;
- public bootstrap for the structural TRM checkpoint;
- independent functional validation;
- persistent and cross-process authority mechanisms.

---

## Research discipline

The repository is intentionally hostile to claims that exceed the evidence.

A mechanism test proves the mechanism it exercises. It does **not** automatically prove intelligence, competence, alignment, generalization, or real-world utility.

Generated code should be treated as untrusted regardless of whether it was written by a human, an LLM, or another synthesis system. Important transitions should have narrow scope, explicit contracts, negative tests, deterministic identities where claimed, and independent validation of observable behavior.

A demo should not be made to pass by quietly widening authority.

In particular, convenience is not enough justification for hidden `eval`, `exec`, implicit subprocess execution, arbitrary imports, or automatic execution of generated artifacts.

If execution is added later, it should be a separately designed, separately authorized, separately qualified boundary.

---

## Release and provenance

This source tree is the **Elpis2.1.4** release line. Published release tags are treated as immutable. Any tracked change to a sealed tree requires a successor release identity rather than a post-seal manifest rewrite.

Release identities live under:

```text
manifests/
```

Model provenance and third-party notices live under:

```text
THIRD_PARTY_NOTICES.md
LICENSES/
docs/
```

Elpis code is MIT licensed unless a file or bundled third-party component states otherwise.

The standard for the project is reproducibility: important claims should survive independent installation, deterministic identity checks, adversarial tests, real-model execution where relevant, and external functional oracles.

---

**Christ is King**
