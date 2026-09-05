# StreamingRegexIngress

**Status:** `QUALIFIED_SUCCESSOR_COMPONENT`
**Runtime admission:** `FALSE`

## Role

`StreamingRegexIngress` is the native bounded lexical producer for the currently
qualified Regex grammar.

It is a byte-exact native replacement candidate for the previously qualified
Python `regex_ingress.py` producer.

The component:

- streams raw UTF-8 bytes with a bounded carry window;
- uses PCRE2-8 in UTF/UCP/caseless mode;
- emits provisional lexical evidence only;
- composes only locally unambiguous bounded task candidates;
- fails closed on contradictory evidence;
- computes source, matched-text, evidence, and candidate SHA-256 identities;
- emits deterministic canonical UTF-8 JSON.

## Authority boundary

Every emitted record remains:

- `candidate_status=PROPOSED_UNADMITTED`
- `semantic_authority=false`
- `admission_authority=false`
- `execution_authority=false`
- `runtime_admission=false`

The component does not:

- admit semantic truth;
- mutate the persistent Semantic Fabric base graph;
- extend the P4 relation enum;
- create a RetrievalBundle;
- map semantics to Grid81;
- execute generated behavior.

## Regex engine dependency

The qualified native candidate uses PCRE2-8. Qualification binds the observed
PCRE2 version and requires byte-exact parity against the frozen qualified Python
oracle over the bounded grammar corpus.

This component remains runtime-unadmitted until its native output is connected
directly to native HACF + QueryLocalProposalIngress without Python in the path.
