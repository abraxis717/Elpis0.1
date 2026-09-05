# Elpis

**Structural AI research for low-authority learned reasoning, explicit topology, and falsifiable alignment mechanisms.**

Current public release: **Elpis2.1.0**

## Abstract

Elpis is a research system for separating learned inference from the authority that defines computational state, legal transitions, validation, and execution. Its central hypothesis is that some alignment problems become more tractable when learned models operate inside explicit geometric and topological structures rather than implicitly owning the entire reasoning process.

The current system combines typed semantic requests, deterministic projection into a bounded structural substrate, learned structural guidance, digest-bound authority transitions, deterministic materialization, source construction, and static validation. A separate public reference path runs a real pinned FPRM model on Sudoku.

Elpis is not presented as a solved alignment system, a general intelligence, or an autonomous coding agent. The repository is organized so that working mechanisms, negative results, and unfinished research can be distinguished and independently tested.

---

## Current validated status

The most important information is what works now.

| Surface | Current status | Direct falsifier |
|---|---|---|
| Elpis2.1.0 Python wheel | **Working** | Install outside the repository and import the runtime |
| Public FPRM model bootstrap | **Working** | Fetch, hash-verify, strict-load |
| Real FPRM Sudoku inference | **Working** | Run CPU inference and validate the board |
| Typed semantic request graph | **Working** | Contract and digest tests |
| Semantic structure → Grid81 Projector | **Working** | Projection, rejection, determinism tests |
| Frozen structural TRM guidance path | **Working when checkpoint is supplied** | Admission and topology qualification |
| Digest-bound validated-source runtime | **Working** | End-to-end structural runtime tests |
| Canonical Python AST policy | **Working** | Positive/negative policy convergence tests |
| Autonomous arbitrary Python synthesis | **Not working yet** | Blind `merge_intervals` test fails functionally |
| Natural-language → trusted semantic graph | **Not implemented** | No production semantic compiler exists |
| Generated-source execution | **Not implemented** | Runtime explicitly grants no execution authority |

The working release therefore already contains a real structural system and real learned inference. The principal missing capability is not plumbing: it is autonomous implementation synthesis from the resolved structure.

---

## Quick start

### Install the published wheel

The PyPI project name `elpis` is currently owned by an unrelated automatic-speech-recognition project. Do not use `pip install elpis` to install this repository.

Install the Elpis2.0.0 GitHub release wheel instead:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip

python -m pip install \
  https://github.com/abraxis717/Elpis0.1/releases/download/Elpis2.0.0/elpis-2.0.0-py3-none-any.whl
```

Fetch the pinned public FPRM checkpoint:

```bash
elpis model fetch
```

Verify it:

```bash
elpis model verify
```

Run a real CPU inference:

```bash
elpis sudoku solve \
  --puzzle '.34678912672195348198342567859761423426853791713924856961537284287419635345286179' \
  --device cpu
```

The model is loaded only after its pinned identity and state ABI are verified.

The Sudoku reference model is deliberately narrow. Sudoku capability is evidence of Sudoku capability, not evidence of general reasoning.

---

# 1. Research premise

## 1.1 Alignment through separation of authority

A conventional learned system can collapse several roles into one model: interpretation, representation, planning, proposal, validation, and practical authority over the output.

Elpis separates those roles.

A learned model may propose a structural change without owning the rules that define the structure. A decoder may construct candidate source without acquiring execution authority. A validator may reject an artifact without gaining authority to repair arbitrary state. A terminal result may carry evidence without becoming a reusable capability.

This produces a recurring architectural distinction:

```text
learned computation
        |
        v
proposal

deterministic contracts
        |
        +--> identity
        +--> legal state
        +--> transition rules
        +--> authority
        +--> validation boundary
```

The alignment hypothesis is modest but concrete: reducing the authority assigned to learned components may make their failures easier to contain, inspect, reproduce, and correct.

This is an architectural hypothesis. Elpis does not claim that bounded authority alone solves alignment.

## 1.2 Geometric and Topological Intelligence

"Geometric/Topological Intelligence" is the project term for representing meaningful parts of a reasoning problem as explicit relational structure rather than leaving all structure latent inside model activations.

The current bounded substrate is Grid81. It provides an 81-cell structural control space with explicit lanes, ranks, masks, bindings, invariants, residuals, and transition rules.

A typed semantic request may describe entities, operations, dependencies, relations, constraints, quantities, and outputs. The deterministic Projector maps the supported structural content of that graph into Grid81. A learned structural model can then operate on the resulting bounded topology.

The present architecture is therefore approximately:

```text
task semantics
     |
     v
typed semantic graph
     |
     v
deterministic Projector
     |
     v
Grid81 structural topology
     |
     v
learned proposal / refinement
     |
     v
resolved topology
     |
     v
bounded downstream capabilities
```

The learned model does not silently define the topology it is asked to modify.

Elpis does not claim that Grid81 is a universal representation or that intelligence is fundamentally geometric. It provides a concrete experimental substrate on which those claims can be tested.

---

# 2. Working architecture

## 2.1 Semantic request graph

The structural path begins with `P0SemanticRequestV1`, a canonical relational task representation independent of Grid81.

It can encode explicit:

- entities and data types;
- operations and ordered arguments;
- constraints and negation;
- directed relations;
- directed dependencies;
- integer quantities;
- declared outputs.

The representation is deterministic and digest-bound. It enforces referential integrity and rejects malformed graphs rather than silently repairing them.

Implementation:

```text
src/elpis_reference/structural_guidance/_authority/elpis_p0/semantic_ir.py
```

This is a representation contract, not a natural-language parser.

## 2.2 Deterministic Projector

The Projector converts the supported semantic structure into the bounded Grid81 substrate.

Its output includes structural state, frozen/writable masks, semantic bindings, invariants, lane assignments, residual features, trace records, fingerprints, and content digests.

Unsupported, contradictory, or over-capacity inputs produce explicit typed rejection states.

Implementation:

```text
src/elpis_reference/structural_guidance/_authority/c2r6p0/
```

The Projector owns semantic-to-structural assignment. The learned model does not.

## 2.3 Learned structural guidance

Elpis contains a frozen structural TRM0 guidance path separate from the public Sudoku FPRM model.

When guidance is explicitly enabled and the correct checkpoint is supplied, the path is:

```text
semantic request
    → Projector
    → structural admission
    → frozen TRM0 refinement
    → resolved structural topology
```

Guidance remains opt-in by default:

```text
enabled = false
```

The qualified structural checkpoint currently has SHA-256:

```text
e58e44c9227d68971d0ab5f5e4f0eaf2e05d4faa97ec8232108aa73898273129
```

It is not yet distributed through the same public-bootstrap path as the FPRM Sudoku model.

## 2.4 Authority and materialization

Elpis separates observation from permission to act.

Resolved topology, structural materialization, planning, decoding, source emission, and validation each have distinct contracts and one-shot authority transitions. Important artifacts are digest-bound to the exact upstream state they consume.

A terminal structural runtime result carries:

```text
authority_granted = 0
validation_authorized = false
execution_authorized = false
```

Authority is intentionally non-transitive.

## 2.5 Validated-source runtime

The current production composition path is:

```text
P0SemanticRequestV1
    → Projector
    → structural guidance
    → ResolvedStructuralTopologyV1
    → ResolvedStructuralMaterializationV1
    → PlanningInputV1
    → StructuralPlanningArtifactV1
    → DecoderSpecificPlanV1
    → DecoderSourceInputV1
    → DecodedSourceArtifactV1
    → StructuralValidationEvidenceV1
    → StructuralGuidanceRuntimeResultV1
```

The terminal status is either:

```text
VALIDATED_SOURCE
```

or:

```text
VALIDATION_REJECTED
```

Generated source is not compiled, imported, invoked, or executed by this runtime.

## 2.6 Canonical Python AST policy

Python source is inspected through the canonical policy in:

```text
src/elpis/python_ast_policy.py
```

The policy rejects malformed syntax, missing entrypoints, imports, scope mutation through `global` or `nonlocal`, and banned calls including `eval`, `exec`, `compile`, `open`, `__import__`, and `breakpoint`.

A successful policy decision is:

```text
passed = true
code = AST_VALID
```

`AST_VALID` means the source satisfies the static policy. It does not mean the program is functionally correct.

## 2.7 Public learned reference model

The public FPRM path is independently useful and independently testable.

The release model is:

```text
FPRM.Samsung_TRM
```

Pinned SHA-256:

```text
6daec5f499d115beb14e23f3a9cf56d1166b99c1ccd36b185a19ea5dfec9a137
```

The public wheel can fetch the checkpoint into a writable user cache, verify it, strict-load it, perform real CPU inference, and later reuse the verified cache offline.

This reference path does not grant the model task authority beyond its native Sudoku domain.

## 2.8 Feedback and bounded RELEASE

The repository also contains qualified mechanisms for tracing typed task failures back to pre-existing structural support.

A failure may identify support that is eligible for bounded `RELEASE`, widening an existing search space. It may not convert the failure into arbitrary authority to assert new structure.

Relevant implementation includes:

```text
src/elpis_reference/feedback_refinement.py
src/elpis_reference/projector_release.py
components/DarwinianMatrix/
```

Mechanism correctness is tested. Generalized task-improvement efficacy remains a separate research question.

---

# 3. Reproduction and falsification

Elpis is intended to be easier to disprove than to market.

## 3.1 Release integrity

From a source checkout:

```bash
python tools/verify_public_release.py
python tools/ci_secret_scan.py .
```

The release verifier should reject inconsistent tracked-file identities or malformed distribution authority.

## 3.2 Real model integrity

From an installed Elpis2.0.0 wheel:

```bash
elpis model fetch
elpis model verify
```

A modified or incompatible checkpoint should fail verification.

## 3.3 Real Sudoku inference

```bash
elpis sudoku solve \
  --puzzle '.34678912672195348198342567859761423426853791713924856961537284287419635345286179' \
  --device cpu
```

The result is falsified if the runtime fails to solve the qualified case, alters a fixed given, or produces an invalid completed board.

## 3.4 Structural runtime

From the repository root:

```bash
export PYTHONPATH="$PWD/src:$PWD/components:$PWD/components/Pipeline/P0ControlProtocol/src:$PWD/components/TRMFractalSpine/src"

python -m pytest -q \
  tests/test_python_ast_policy_convergence.py \
  tests/test_structural_guidance_structural_validator.py \
  tests/test_structural_guidance_validated_source_runtime.py \
  tests/test_structural_guidance_runtime_admission.py
```

These tests exercise canonical AST-policy convergence, terminal digest integrity, explicit guidance admission, authority-zero results, validation rejection, source tamper detection, and the prohibition on generated-source execution.

Broader mechanism tests are under `tests/`.

## 3.5 Current negative result: autonomous source synthesis

The most useful recent test was intentionally allowed to fail.

Elpis was given a typed semantic representation of `merge_intervals`, the natural-language task, the real frozen structural TRM0, and the complete validated-source runtime. No implementation body was supplied.

The blind result was:

```text
runtime_status = VALIDATED_SOURCE
validation_code = AST_VALID
functional_pass = false
functional_failures = 7 / 7
```

The emitted function contained `return None`.

A positive-control arm used the same semantic input and the same resolved topology but supplied a known-correct body. The downstream source and functional-validation path passed.

The result localizes the current boundary:

```text
semantic representation              working
deterministic projection              working
learned structural guidance           working
resolved topology                     working
materialization                       working
planning transport                    working
decoder normalization                 working
source emission                       working
static validation                     working
autonomous implementation synthesis   not working
```

This negative result is part of the project status, not something to hide behind the successful AST validation.

---

# 4. Repository guide

The front door is intentionally small. Historical milestone detail belongs in `CHANGELOG.md`.

| Path | Purpose |
|---|---|
| `src/elpis_reference/` | Portable Elpis runtime and public model path |
| `src/elpis/` | Canonical shared policies |
| `src/elpis_reference/structural_guidance/` | End-to-end structural-guidance system |
| `components/DarwinianMatrix/` | Structural clamp and Projector authority machinery |
| `components/TRMFractalSpine/` | Structural TRM contracts |
| `components/Pipeline/P0ControlProtocol/` | P0 control and validator mechanisms |
| `tests/` | Direct, negative, determinism, integration, and red-team tests |
| `manifests/` | Release and distribution integrity records |
| `docs/` | Detailed build, testing, architecture, and provenance material |
| `CHANGELOG.md` | Historical development and release chronology |

If you are trying to understand the current system, start with `src/elpis_reference/structural_guidance/`, then read the tests that exercise the component you care about.

---

# 5. Development standard

The repository is intentionally hostile to claims that exceed the evidence.

A mechanism test proves the mechanism it exercises. It does not automatically prove intelligence, competence, alignment, generalization, or real-world utility.

Generated code should be treated as untrusted code regardless of whether it was written by a human, an LLM, or another synthesis system. Important changes should have narrow scope, explicit contracts, negative tests, deterministic identities where claimed, and external validation of observable behavior.

A demo should not be made to pass by quietly widening authority. In particular, convenience is not sufficient justification for adding hidden `eval`, `exec`, implicit subprocess execution, arbitrary imports, or automatic execution of generated artifacts.

If source execution is added in the future, it should be a separately designed, separately authorized, and separately qualified boundary.

---

# 6. Still being developed

## 6.1 Autonomous structural source synthesis

This is the immediate engineering target.

The present deterministic planner transports a supplied implementation body and otherwise falls back to `return None`. A real synthesizer must instead derive a candidate implementation from the semantic request, resolved topology, planning artifact, and source-input binding without being handed the answer.

The first regression target remains the existing blind `merge_intervals` experiment. The target condition is simple:

```text
body_hint_supplied = false
runtime_status = VALIDATED_SOURCE
validation_code = AST_VALID
functional_pass = true
```

After that, the synthesizer must survive unseen tasks rather than overfitting one benchmark.

## 6.2 Natural-language semantic compilation

The typed semantic graph exists. A production system that converts arbitrary language into a trustworthy semantic graph does not.

Future work must address ambiguity, paraphrase invariance, prompt/graph consistency, unsupported semantics, uncertainty, and adversarial input without silently allowing the language model to redefine the Projector.

## 6.3 Public structural-TRM bootstrap

The FPRM Sudoku checkpoint has a qualified public bootstrap path. The frozen structural TRM0 does not yet.

A public structural-guidance model path needs explicit provenance, pinned identity, strict loading, stable cache behavior, and cold-consumer qualification.

## 6.4 Functional validation

Static AST validation is intentionally narrow.

Future generated-code work should use independent functional oracles such as unit tests, property tests, type checks, domain validators, or separately authorized sandboxes. Those systems should remain distinct from the learned proposer.

## 6.5 Broader alignment architecture

Persistent governance, persistent memory authority, generalized semantic re-projection, hostile same-process isolation, cross-process durable authority, external cryptographic attestation, SAM integration, generalized relational/ECS dynamics, autonomous agent operation, and arbitrary generated-source execution remain outside the currently qualified portable system.

---

# 7. Release, provenance, and license

The current public release is `Elpis2.0.0`.

The release tag is intentionally immutable. `main` may contain post-release packaging, testing, and documentation improvements while the tagged release remains fixed.

Exact release identities belong in:

```text
manifests/
```

Model provenance and third-party notices are documented in:

```text
THIRD_PARTY_NOTICES.md
LICENSES/
docs/
```

Elpis code is MIT licensed unless a file or bundled third-party component states otherwise.

The standard for the project is reproducibility: important claims should survive independent installation, deterministic identity checks, adversarial tests, real-model execution where relevant, and external functional oracles.

---

Christ is King
