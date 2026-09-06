# Furyan R0 finite placement contract

This is an independent mathematical falsifier, not allocation authority.
Ranks are exactly the integers 0..8. There are 1..8 operations. Each operation
identifier names its own lane and the operation occupies its assigned rank
in that lane. Different lanes may use the same rank. In each lane all operation
and auxiliary loci are injective.

## Input and rejection

The JSON object has exactly three fields: operations, edges, tails. Missing
edges/tails default to empty lists. Operations is a nonempty list of unique
identifiers matching [A-Za-z][A-Za-z0-9_]{0,63}. Edges are unique triples
[kind,source,target], with existing, different operation endpoints. The three
supported kinds are precedes, route, state_feeds. Multiple different kinds
on a pair are simultaneous obligations. Duplicate triples, malformed types,
unknown references, self edges, malformed identifiers and zero operations
are INVALID_INPUT. More than eight operations, unsupported kinds, unknown
input fields, unsupported tail kinds/relations are OUT_OF_SCOPE. Structural
invalidity takes precedence over unsupported semantics. Cycles are valid
mathematical inputs and UNSAT, not malformed inputs. No constraint is dropped.

A TailRequirement is an object with exactly id, lane, after, relation, kind.
Its unique id follows the identifier grammar; lane and after reference existing
operations, and may differ. relation must be strict_after; kind is CONSTRAINT
or INTERFACE. It demands one distinct locus of that kind in lane, at a rank
strictly greater than the rank of operation after. It has no other semantics.
Tail ids and operation ids occupy separate namespaces.

precedes(A,B): rank(B) >= rank(A)+1; no witness.
route(A,B): rank(B) >= rank(A)+2, one ROUTE witness in B's lane with
rank(A) < witness_rank < rank(B).
state_feeds(A,B): rank(B) >= rank(A)+2, one MEMORY witness in A's lane with
the same strict interval. Every edge has its own witness, even if another
edge has identical endpoints but a different kind.

No pinning, arbitrary domains, negative/negated predicates, mutation hazards,
EXPANSION, entity/quantity meanings or implicit P0 constraint/interface
derivations are admitted. Automatic P0 translation is conservatively
OUT_OF_SCOPE for all P0 objects in R0; the test-only production differential
constructs an explicitly audited core instance independently. There is no
production import in the oracle or certificate validator.

## Canonical identity and output

The Python API solve accepts JSON-compatible inputs, also allowing tuples
where JSON arrays occur. UTF-8 canonical JSON uses sort_keys=True,
separators=(',',':'), ensure_ascii=False, allow_nan=False. Normalize operations
lexicographically, edges lexicographically by triple, tails by id. Sequence
order and tuple/list representation do not affect normalized identity.
Identifiers are significant; isomorphic renaming is only a corpus quotient.
Non-JSON Python transports return INVALID_INPUT with the canonical identity
{"transport":"non_json"}; JSON-compatible malformed inputs bind their raw
canonical JSON. Valid unsupported inputs bind their normalized form.

SHA-256 of canonical normalized input is input_digest. model_digest is SHA-256
of the exact UTF-8 bytes of this spec. The result schema is furyan.result.r0.
It contains normalized_input, input_digest, model_digest, status, reason,
certificate (null unless SAT), certificate_digest (null unless SAT), and
result_digest. result_digest hashes all other result fields. Reasons are
stable diagnostic identifiers; UNSAT reason is finite_search_exhausted.

A certificate has exactly schema=furyan.certificate.r0, model_digest,
input_digest, operations (map identifier to integer rank), loci (ordered list
of {id,kind,lane,rank}). Edge witness ids are edge:KIND:SOURCE:TARGET. Tail ids
are tail:ID. Loci sort by id. certificate_digest hashes the entire certificate.
No identity uses time, randomness, UUID, process, path, environment, network,
model inference or search instrumentation. Status vocabulary is SAT, UNSAT,
OUT_OF_SCOPE, INVALID_INPUT. There is no UNKNOWN or execution cutoff.

Canonical SAT choice is lexicographically least operation-rank vector in
sorted operation order, then lexicographically least witness rank vector in
sorted locus-id order, among all feasible assignments. Lane names/kinds/ids
are fixed by input. No claim of canonicality under operation renaming.

## Completeness argument

Search enumerates operation ranks in canonical order, propagating lower and
upper bounds along positive-gap edges. Bounds start at 0 and 8; for each edge
u->v with gap g, low(v)>=low(u)+g and high(u)<=high(v)-g. Assigned variables
have singleton bounds. Removing branches with crossed bounds is sound.
The propagation reaches a fixed point or contradiction after finitely many
integer bound changes. A lane with more than eight demands is impossible,
because its operation occupies one of nine cells. At each complete operation
assignment, enumerate the finite allowed ranks for every auxiliary demand,
excluding that lane's operation rank. Solve the resulting matching exactly
using depth-first injective assignment with backtracking, in locus-id/rank
order. Each depth is at most 64 after capacity pruning. No greedy commitment
or incomplete cutoff is used. Every feasible rank assignment survives bounds;
every feasible auxiliary injection occurs in the enumeration. Exhaustion
therefore proves UNSAT. First success implements the specified lexicographic
certificate. Search is potentially exponential but always finite for finite
admitted input.

The separate validator reads a supplied certificate and checks fields, exact
coverage, ranks, edge gaps, witness lane/kind/strict interval, tails, collisions
and all digests directly. It does not invoke search, matching or feasibility.
Shared transport normalization and serialization carry no placement authority.
A validator accepts any valid SAT certificate, not only the canonical one.

## Qualification universe, minimality and limitations

Core exhaustive universe for n=1,2,3: every subset of the 3*n*(n-1) distinct
possible directed triples, including cycles and simultaneous kinds. Labeled
counts are 1,64,262144. Quotient by all n! operation permutations, choosing the
least canonical serialized instance; bijective renaming transports ranks,
lanes and witness identities and preserves SAT and earliest-baseline failure
(the baseline tests exact auxiliary feasibility). Thus the quotient is complete
for these properties. Tests record quotient counts and sum of orbit sizes.
The independent reference enumerates all 9^n operation vectors and all finite
auxiliary rank products, rejecting constraints directly. A precomputed truth
mask of edge gaps only accelerates these same rank vectors; it is not solver
code or pruning authority shared with the candidate.

One-operation tails: exhaust all CONSTRAINT/INTERFACE count pairs of total
0..9 (55 cases), with every tail necessarily in/after that one operation.
For total<=8 SAT at operation rank 0; total>=9 UNSAT by nine-cell capacity.
All larger counts reduce to this analytic UNSAT class; arbitrary id renamings
cannot affect existence. This covers every one-operation admissible shape
up to kind counts and the saturated overflow class, not infinitely many names.

For n=4..8 use a fixed deterministic corpus of empty graphs, chains, cycles,
route fan-ins, memory fan-outs, dense forward graphs, explicit tail capacities
and matching-sensitive constructions. Independently validate every SAT result;
compare all to a separate exhaustive reference (which may enumerate only the
connected constrained part and explicitly free isolated operations at rank 0).

Minimality orders core cases by operation count, edge count, canonical JSON.
Report first and all ties at the smallest (operation count,edge count), with
search count. This is a CORE (no tails) minimality claim. For the full tail
model, additionally search n=1..2 with up to two total edges/tails, including
all tail lanes, bounds and kinds, and report separately. No global minimality
claim over unbounded tail counts is made.

Mutation qualification changes executable source in memory, never production
files. Each mutant must fail its designated guard with the exact reason.
Some guards (notably route +2, implied by a strict integer witness) are
logically redundant in complete feasibility. Such equivalent semantic mutants
are tested at their explicit rule primitive; record this honestly as a rule
unit kill, not an end-to-end SAT/UNSAT disagreement. Boundary/domain tests
likewise isolate their rule to avoid wrong-reason collision kills.

Production parity is restricted to the audited core subset in the evidence
report. Production DECOMPOSITION_REQUIRED is an algorithm outcome, not UNSAT.
Only a recorded run of the actual shipped allocator, with exact input bytes,
digests and diagnostics, supports a shipped strategy counterexample. It does
not imply the legacy sidecar projector maps semantic nodes into cells, or that
all Elpis semantics are represented by Furyan.
