# P4 — Evidence Typing and Admission Architecture

## Pipeline position

```
User query
  → query atomization and initial semantic overlay
  → P1 embedding references and metric neighborhoods
  → P2 context-deficit evaluation
  → P3 R3 retrieval bridge
  → verified RetrievalBundles
  → transport-level evidence expansion
  → P4 evidence typing and admission  ← THIS PHASE
  → typed-evidence semantic view
  → later P2 context re-evaluation
  → later bounded semantic-view compilation
  → later deterministic projector
  → later Grid81 structural substrate
```

## Definitions

| Term | Definition |
|------|-----------|
| **P3 EVIDENCE_CHUNK** | Verified retrieved transport material. A P3 retrieval item attachment containing verified text, chunk digest, and provenance. |
| **P4 EVIDENCE_SPAN** | Exact byte range `[byte_start, byte_end_exclusive)` inside one verified evidence chunk. Byte offsets, not Unicode code points. |
| **P4 CLAIM_CANDIDATE** | Externally supplied proposed semantic claim. A proposal only — not yet admitted. Contains claim type, payload, source spans, polarity, modality, scope, confidence. |
| **P4 RELATION_CANDIDATE** | Externally supplied proposed typed relation. A proposal only — not yet admitted. Contains relation type, evidence object, target object, roles, source spans, confidence. |
| **P4 ADMISSION_DECISION** | Deterministic result of applying sealed admission policy and structural validation to a candidate. Either ADMITTED or REJECTED with a specific reason. |
| **P4 ADMITTED CLAIM** | A semantic node of type `EXTRACTED_CLAIM` plus a provenance-bearing assertion. Stable identity derived from claim payload digest and semantic flags only. |
| **P4 ADMITTED RELATION** | A semantic hyperedge of an allowed relation type plus a provenance-bearing assertion. Stable identity derived from relation type, canonical participants, and semantic flags only. |
| **P4 TYPED EVIDENCE VIEW** | The P3 retrieval-expanded view plus the immutable P4 evidence-admission layer. Consumable by later context evaluation and projection stages. |

## Transport-to-Semantic boundary

```
text transport evidence
+ exact source span (byte range in verified chunk)
+ externally supplied semantic proposal (claim or relation)
+ sealed admission policy
  ↓
validated candidate claim OR validated candidate relation
  ↓
admit or reject (deterministic)
  ↓
immutable typed-evidence layer
```

### What P4 does NOT do

P4 does NOT establish that a claim is ultimately true. P4 establishes only that:

- The proposal is exactly grounded in admitted source material.
- The proposed semantic object is well-formed.
- The proposed relation uses a permitted type and role structure.
- The proposal satisfies the sealed admission policy.
- Every admitted object retains exact provenance and authority bounds.

## Authority separation

### Evidence transport is NOT semantic truth

A retrieval score, fusion rank, or lexical match is transport evidence — not a claim about truth. Transport rank has no admission authority.

### Exact source span is NOT automatically a claim

Extracting a byte span from a verified chunk proves nothing about semantics. A span is merely the anchoring point for an externally proposed claim.

### Candidate claim is NOT automatically admitted

Even a well-formed candidate claim with valid source spans requires admission against a sealed policy. Admission is a separate step with its own authority ceiling.

### Admitted SUPPORTS does NOT mean globally proven true

An admitted `SUPPORTS` relation means the external typer proposed that the source material supports the target claim, and that proposal passed structural and policy validation. It does NOT mean the target claim is true.

### Admitted CONTRADICTS does NOT resolve the conflict

When both `SUPPORTS` and `CONTRADICTS` exist for the same target, P4 retains both. P4 does not cancel, average, or resolve conflicts. Conflict resolution is downstream.

### Embedding proximity has NO admission authority

Embedding similarity cannot admit, reject, merge, or deduplicate claims or relations. Semantic identity is determined by structural identity rules only.

### Retrieval rank has NO semantic authority

Fusion rank, lexical rank, and dense rank are transport metadata. They do not affect semantic identity, admission decisions, or authority.

### Model confidence has NO truth authority

The confidence key in a candidate is metadata from the evidence typer. It affects admission eligibility against policy thresholds but does NOT confer truth authority.

### P4 cannot elevate authority above sealed ceilings

Default P4 v1 authority ceilings:
- `EXTRACTED_CLAIM` assertion: no higher than `ADVISORY`
- `MENTIONS`, `DEFINES`, `PROVIDES_CONTEXT_FOR`: no higher than `ADVISORY`
- `SUPPORTS`, `CONTRADICTS`, `QUALIFIES`, `LIMITS_SCOPE_OF`: no higher than `PROVISIONAL`

P4 must never promote a relation to `REFERENCE` or `CANONICAL` under the default policy.

## Graph-edge provenance

P3 established: graph-edge provenance status is `UNAVAILABLE`.

P4 preserves this status. P4 does NOT synthesize, infer, or substitute a graph-edge provenance digest. The `UNAVAILABLE` status is recorded in every admission receipt.

## Semantic identity rules

### Admitted claim identity

Binds: node type (`EXTRACTED_CLAIM`), claim payload digest, stable semantic flags.

Does NOT bind: source span, RetrievalBundle, retrieval rank, item authority, typer profile, typing bundle, confidence key, admission decision, query overlay, timestamp.

**Result:** the same semantic claim extracted from different evidence sources produces ONE stable claim-node identity with multiple assertions.

### Admitted relation identity

Binds: semantic relation type, canonical participant set, relation payload or qualifier digest, stable semantic flags.

Does NOT bind: source RetrievalBundle, retrieval rank, provider confidence, provider identity, admission decision, query identity.

**Result:** the same semantic relation supported by multiple evidence sources produces ONE stable hyperedge identity with multiple assertions.

### Assertion identity

Every admitted claim and relation receives one or more P0 assertions. Assertion provenance = admission receipt HACF package digest.

## Nondependency boundary

P4 reusable source must NOT depend on:
- ACTV1, DimpleTransformer, any model checkpoint/vocabulary
- Grid81, projector codebooks, StructuralOracle, StructuralRolloutController, DarwinianMatrix, ECRF
- Microsoft GraphRAG, GPU execution, network services
- Python runtime, local model ports, machine-specific filesystem paths

The reusable public ABI must remain C-compatible.

## Module structure

```
include/elpis_semantic/
  evidence_typer_profile.h        — Provider profile ABI
  evidence_span.h                 — Exact source-span ABI
  evidence_claim_candidate.h      — Claim candidate ABI
  evidence_relation_candidate.h   — Relation candidate ABI
  evidence_typing_bundle.h        — Typing proposal bundle ABI
  evidence_admission_policy.h     — Admission policy ABI
  evidence_admission_decision.h   — Admission decision ABI
  evidence_admission_receipt.h    — Admission receipt ABI
  evidence_admission.h            — Evidence-admission layer ABI
  typed_evidence_view.h           — Typed-evidence read-only view ABI

src/evidence/
  evidence_typer_profile.c        — Provider profile implementation
  evidence_span.c                 — Source-span validation
  evidence_claim_candidate.c      — Claim candidate implementation
  evidence_relation_candidate.c   — Relation candidate implementation
  evidence_typing_bundle.c        — Typing bundle implementation
  evidence_candidate_validate.c   — 10-stage validation pipeline
  evidence_admission_policy.c     — Admission policy implementation
  evidence_adjudicator.c          — Admission decision engine
  evidence_semantic_builder.c     — Semantic object construction
  evidence_admission_segment.c    — Admission segment construction
  evidence_admission_layer.c      — Immutable admission layer
  typed_evidence_view.c           — Typed-evidence read-only view
  evidence_writer.c               — Canonical serialization
  evidence_reader.c               — Verified deserialization

tests/evidence/
  test_typer_profile.c
  test_evidence_span.c
  test_claim_candidate.c
  test_relation_candidate.c
  test_typing_bundle.c
  test_admission_policy.c
  test_adjudicator.c
  test_semantic_builder.c
  test_admission_segment.c
  test_typed_evidence_view.c
  test_evidence_persistence.c
  test_evidence_determinism.c
  test_evidence_boundaries.c
```

## Stop boundary

P4 ends at the typed-evidence semantic view. P4 does NOT implement:
- Context-sufficiency decisions
- Projector logic
- Grid81 mapping
- TRM integration
- StructuralOracle, StructuralRolloutController, DarwinianMatrix, ECRF
- Runtime admission
