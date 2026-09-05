# RegexHACFQueryIngress

**Status:** `QUALIFIED_SUCCESSOR_COMPONENT`
**Build-system admission:** `TRUE`
**Runtime admission:** `FALSE`

## Role

`RegexHACFQueryIngress` is the bounded native composition boundary joining:

1. `StreamingRegexIngress` v1 stable native ABI;
2. native HACF lexical corpus + immutable context graph;
3. provenance-bound `RegexHACFContextProposalR1` construction;
4. `QueryLocalProposalIngress` atomic query-local batch publication.

The caller owns the HACF corpus and context graph. This component queries them
but does not ingest documents, create edges, or mutate either object.

## Public ABI

The public C-compatible header is:

`include/regex_hacf_query_ingress.h`

The result is opaque and exposes read-only access to source/proposal/HACF/query
overlay identities, candidate IDs, batch disposition, and authority state.

## Authority

All candidate material remains `PROPOSED_UNADMITTED`.

This component does not:

- admit semantic truth;
- mutate the persistent Semantic Fabric base graph;
- extend P4;
- create a canonical RetrievalBundle;
- introduce embeddings or vectors;
- map semantics to Grid81;
- authorize execution;
- grant runtime admission.

## Qualification boundary

Qualification proves exact identity parity with the already-closed full native
Regex -> HACF -> QueryLocalProposalIngress chain for the bounded R1 fixture and
task family.

Repository build authority uses the real narrow Semantic Spine support
(snapshot_manifest.c and snapshot_view.c) and does not compile the former
qualification-only semantic link-compat shim.

Top-level build-system admission is qualified. Runtime admission remains false.
