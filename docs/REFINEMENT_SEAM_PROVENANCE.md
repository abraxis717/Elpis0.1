# Refinement seam provenance

The public task-residual contract in `src/elpis_reference/semantic_refinement.py`
is a platform-neutral promotion of the first-party R7A/R7CR3R1 qualification
lineage.

Source identities recovered by the Public C2 promotion audit:

- R7A task residual bridge:
  `c159a3a4da8702ef4989663e528032d6cd112b96d561aa8948aea924951534c6`
- R7CR3R1 mechanism runner:
  `332da7bc7de58922f7e0b21efac4f82a247ce331ea4636f2d4a804999c31ce2d`
- R7CR3R1 deterministic result:
  `2b279920104eaf750f3bcd35b916f7ad28cdf25036bca14d124a52f4fd8aa553`

The promoted contract preserves the qualified R7A domain-separated digest
formats for task diagnostics, task residuals, structural observations, and
resolved residuals. Public tests reproduce the exact frozen R7CR3R1
diagnostic, residual, and resolution digests.

C2R2 promotes the RELEASE-planning portion of the exact R7A source above into
`src/elpis_reference/projector_release.py`. The semantic contract remains in
`semantic_refinement.py`; the adapter consumes that contract and constructs the
existing canonical DarwinianMatrix `ClampTransaction`.

The promoted mechanism preserves these qualified R7A behaviors:

- release targets come only from resolved pre-existing structural support;
- inactive resolved cells are deterministic no-ops;
- current clamp owners are derived from ClampState;
- task-derived proposals are RELEASE only;
- the transaction is bound to the current ClampState digest;
- canonical Projector owner and stale-state rejection remain authoritative.

`ClampProposal.evidence_digest` on this path is the originating task diagnostic
digest. It binds the release request but is not a historical proof of the
evidence that originally created the active clamp because ClampState does not
retain that per-cell evidence digest.

C2R3 composes this already-promoted RELEASE boundary with the existing pinned
Samsung reference runtime. `execute_samsung_feedback_step` accepts a
structurally valid prior proposal, a typed task diagnostic, a pre-existing
reverse-trace index, and canonical ClampState. The diagnostic subject digest
must bind to the exact prior proposal digest before reverse tracing or any
Projector mutation. It executes at most one
task-derived RELEASE transaction and at most one learned re-proposal call.

The learned call receives only the revised Sudoku support tuple derived from
ClampState. Active clamps become givens; inactive/released cells become zero
before the existing deterministic Sudoku token encoder maps them into model
tokens. The task diagnostic, residual, reverse trace, and Projector receipt are
not arguments to the learned solver.

The public C2R3 E2E is deliberately a mechanism-composition control. It uses the
real pinned checkpoint and proves that a predeclared task residual can reopen
one existing support cell and trigger a validated learned re-proposal while
surviving clamps remain preserved. It does not claim that the generic task
failure is a production validator ingress or that the resulting proposal is a
generalized task improvement.

C2R4 binds the real R0/P0 validator boundary into this seam. The production
R0 AST adapter exposes the exact artifact digest and typed `ValidatorEvidence`
from `PythonASTValidator`. A projection trace is frozen from the actual P0
`StructuralProjection` before validation, assigning domain-separated semantic
object, topology vertex, P7 capsule, and observation identities.

Task-validator failure selects only the pre-existing semantic `validation`
object. Validator line/offset details are committed only through
`details_digest`; they do not become structural coordinates. Reverse trace maps
that semantic object to its pre-existing P7 support, after which the already
qualified canonical RELEASE adapter applies current-owner and stale-state
protections.

P0 refinement validation is separately classified: scope/shape/input-binding
rejections remain `STRUCTURAL_REJECTION` and cannot enter the task-residual
path.

This closes production P0 validator ingress and production
projection→semantic/topology/P7 trace binding. It does not establish
artifact→production-structural-proposal lineage, production learned P0
re-proposal, generalized task improvement, or runtime admission.

Red-team hardening after C2R3 changes the release planner contract. A release binding table is committed to the exact pre-release `ClampState` and carries the expected owner plus semantic locus for each eligible target. The planner compares that precommitted owner against the live state instead of deriving the requested owner from live state. Active RELEASE cardinality is fixed at one per traversal. These records are deterministic commitments, not signatures or third-party attestations. The legacy field name `trace_proof_digests` is retained for R7 digest compatibility but denotes trace-record digests, not cryptographic proof.

Sudoku feedback additionally carries the episode's immutable puzzle givens. They may not be released, must be present before traversal, and are used for final validation. Retractable hypothesis RELEASE is search-space widening and is not described as conservative or fail-closed by itself.

The converted model tensor state and safetensors metadata are now verified before model use. This closes the prior gap where a shape-compatible cached safetensors file could pass strict loading without matching a pinned converted-state identity.

Invariant boundary:

- structural rejection does not become a task residual;
- task diagnostics carry no Grid81 cell/value selection;
- reverse trace may resolve a semantic/topology locus to structural support;
- task failure may RELEASE implicated existing support;
- task failure may not ASSERT or REPLACE structural claims;
- learned input is derived only from revised canonical clamp support;
- the learned TRM does not receive task semantics, task diagnostics, residuals,
  reverse-trace records, semantic sidecars, or Projector receipts;
- one C2R3 feedback traversal is bounded by `run_id + refinement_step_index`;
- generalized task improvement and production validator ingress remain unproven;
- runtime admission remains false.
