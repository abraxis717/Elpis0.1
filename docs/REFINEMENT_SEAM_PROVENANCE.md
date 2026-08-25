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

Invariant boundary:

- structural rejection does not become a task residual;
- task diagnostics carry no Grid81 cell/value selection;
- reverse trace may resolve a semantic/topology locus to structural support;
- task failure may RELEASE implicated existing support;
- task failure may not ASSERT or REPLACE structural claims;
- the learned TRM does not receive task semantics or task diagnostics;
- learned re-proposal remains outside C2R2;
- runtime admission remains false.
