# StreamingRegexIngress

**Status:** `QUALIFIED_SUCCESSOR_COMPONENT`
**Runtime admission:** `FALSE`

## Role

`StreamingRegexIngress` is the native bounded lexical producer for the currently
qualified Regex grammar.

This revision exposes a versioned C-compatible library ABI so downstream native
components no longer need to include the C++ implementation source.

## Stable ABI

Public header:

`include/streaming_regex_ingress.h`

The v1 ABI is opaque-result based. Callers submit raw bytes plus a bounded
streaming chunk size and receive deterministic read-only views for:

- canonical complete Regex result JSON;
- canonical ingress JSON;
- canonical composition JSON;
- source SHA-256 and source byte count;
- lexical evidence IDs, pattern IDs, and lexical anchors;
- candidate IDs;
- ambiguity count and fail-closed disposition.

The implementation owns all returned storage until
`elpis_streaming_regex_result_destroy_v1`.

C++ implementation objects are not part of the ABI.

## Qualification

The ABI must remain byte-exact with the frozen qualified Python R1 oracle over
the complete previously-qualified 196 valid + 21 malformed-UTF8 case/chunk
matrix.

The native Regex -> HACF -> QueryLocalProposalIngress chain is additionally
qualified through this public ABI, with no textual `.cpp` source inclusion and
exact identity parity against the previous full-native closure.

## Authority boundary

All emitted proposal material remains `PROPOSED_UNADMITTED`.

This component does not grant semantic truth, admission, execution, or runtime
authority. It does not extend P4, create a RetrievalBundle, or assign Grid81
semantics.

Runtime admission remains false.
