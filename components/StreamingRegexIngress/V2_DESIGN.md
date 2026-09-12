# StreamingRegexIngress V2

Implementation available; runtime admission remains **false**. This is a
successor implementation, not a reseal of the V1 qualification or a generic
regular-expression execution service. See `V2_QUALIFICATION.md` for measured
results, commands and qualification limits.

## Compatibility boundary and the unavoidable representation change

The V1 entry point, header, carry rejection, schema and result accessors remain
available. V1 still stages the entire accepted input and requires
`data_len <= carry_bytes`; chunk size is only transport segmentation.

V1 canonical evidence includes the exact original `matched_text`, its SHA-256,
absolute byte offsets, payload, source SHA-256 and authority fields. The evidence
ID hashes that object. Consider all prefixes `at` + W, where W is an arbitrary
length-n sequence of spaces and tabs. Appending `least 1` makes W part of a
recognized match. There are 2^n possible W values, each requiring a different
exact `matched_text`. An implementation retaining only B bits before that
suffix cannot distinguish them for n > B. Writing tentative text to an external
spool would just move the unbounded pending storage elsewhere. Hashes alone
cannot reconstruct W. Thus bounded pending memory and byte-exact V1 canonical
output for *every* caller-selected V1 carry are incompatible requirements.

V2 therefore retains up to 4,096 original bytes per pending match, plus a running
match SHA-256. Matches of at most 4,096 bytes produce byte-exact V1 evidence and
IDs, even in a much longer source. For longer matches:

* `matched_text` is absent, not shortened or normalized;
* `matched_text_omitted` is true;
* the evidence schema is `elpis.regex-lexical-evidence.v2`;
* exact match SHA-256, absolute offsets, pattern, payload and source identity
  remain present;
* the evidence ID is computed over this explicitly different representation;
* the ingress schema is v2 if any evidence uses this representation.

Composition stays v1. Candidate IDs depend on payload and source identity, so
this necessary evidence representation change does not change candidate IDs or
ambiguity decisions. V1 itself always returns its original exact text. This is
an explicit limit on **V2 canonical identity compatibility**, not a lexical span
limit. The complete requested V1/V2 byte-identity guarantee is not claimed.

## Architecture choice

PCRE2 partial matching identifies an incomplete match but does not provide a
serializable resumable backtracking/capture state independent of the subject.
Keeping the partial subject would retain unbounded whitespace. A tail-overlap
solution has the same problem.

A fully handwritten tokenizer would duplicate 14 grammar definitions and Unicode
case/word/space/digit semantics. V2 instead compiles the existing `patterns()`
expressions into an ordered Thompson machine. It implements only the syntax
used by this frozen grammar: concatenation, ordered alternatives, bounded greedy
repetition, greedy whitespace loops, named captures and word boundaries. Other
unbounded repetition is rejected at compilation. There is no input-controlled
expression compilation.

PCRE2 is used only for anchored **single-code-point predicates** with the same
UTF/UCP/CASELESS options as V1. ASCII truth tables are precomputed. Unicode
predicates use the linked PCRE2 Unicode tables, including caseless identifier
characters such as Kelvin sign and long s. Compiled predicate code is immutable
and shared; match scratch and predicate results are private to each stream.
There is no PCRE2 backtracking over a source stream or an input window.

## Frozen grammar/state census

All 14 pattern families can span unbounded whitespace. None has an unbounded
identifier, number, intervening word count or non-whitespace repetition.
The following conservative non-whitespace scalar counts include all optional
parts. Single whitespace alternatives may overcount by one, safely.

| Pattern family | Finite state/capture requirement | Non-whitespace bound |
| --- | --- | ---: |
| cmp.gte.at_least | ordered phrases; optional sign; 32 integer + 16 fraction digits | 70 |
| cmp.gt.more_than | same numeric state | 69 |
| cmp.lte.at_most | same numeric state | 67 |
| cmp.lt.less_than | same numeric state | 66 |
| cmp.ne.other_than | same numeric state | 60 |
| cmp.eq.exact | same numeric state | 64 |
| bounds.direct | three identifiers, each at most 128 scalars | 406 |
| role.lower.explicit | identifier, is/as, optional the, lower-role alternatives | 143 |
| role.upper.explicit | identifier, is/as, optional the, upper-role alternatives | 143 |
| coal.strict.negated_touch | at most five intervening words, each at most 64 scalars; ordered negation | 350 |
| coal.strict.positive_width | bounded keyword alternatives; positive[-\s]width takes exactly ONE separator | 21 |
| coal.touching.allowed | bounded noun/modal/also alternatives | 46 |
| coal.reducer.max | bounded reducer/endpoint alternatives | 24 |
| coal.reducer.min | bounded reducer/endpoint alternatives | 24 |

Every `\s+` becomes a resumable loop. The compiler computes the structural
non-whitespace bound from its AST and rejects a grammar exceeding 512 scalars
or 4,096 instructions per pattern. The current compiled grammar has 3,739
instructions in total. Captures retain original bytes, at most 512 bytes per
capture (128 Unicode scalars times four); no captured whitespace loop exists.
V1's Unicode-digit recognition followed by `strtod` rejection is deliberately
preserved rather than inventing new numeric semantics.

## State, ordering and chunk invariance

The incremental UTF-8 decoder retains at most four bytes. It rejects illegal
lead/continuation bytes, overlong encodings, surrogate encodings and code points
above U+10FFFF. Incomplete sequences remain private across feeds; EOF rejects a
truncated sequence. Lexical processing only sees complete validated scalars.

Each pattern maintains ordered candidate starts at absolute source-byte offsets.
Every pattern begins with a word boundary and consumes a word character first.
A boundary is evaluated using the previous and next scalar's PCRE2 word
classification; EOF is non-word. Thus neither transport boundaries nor a
truncated byte sequence can create a boundary.

Each candidate owns ordered machine threads, bounded capture strings, a running
match hash, a bounded inline-text buffer and at most one saved accepted match.
At each scalar, epsilon closure visits a program counter once, keeping the
highest-priority arrival. There are no backreferences or capture-dependent
conditions, so lower-priority arrivals at the same PC cannot improve a future
match. Ordered splits implement V1 alternative priority and greediness. An
accept cuts lower-priority threads but retains higher-priority threads that may
later replace the saved match. This handles numeric fallback and the greedy
intervening words in the negated-touch pattern.

Later starts remain available while an earlier start is unresolved. When the
first viable start resolves, starts before its selected end are discarded and
starts at/after that end remain. This reproduces PCRE2's per-pattern leftmost,
nonoverlapping search without replaying source. Different pattern families
remain independent, preserving intentional overlaps and ambiguity. Final raw
evidence is sorted by start, end and pattern ID using the unchanged canonical
composer.

Feed segmentation does not appear in the transition function. Decoder state,
ordered lexical state and SHA-256 contexts advance from the same sequence of
original bytes/scalars; only finalize supplies EOF. Induction on input bytes
therefore yields identical terminal state for every partition. No evidence or
result handle is externally available before successful finalize. Fatal input,
resource or allocation failure makes the stream terminal and publishes no
result. Ambiguity is distinct from malformed input: a successfully finalized
ambiguous result exposes the original fail-closed disposition.

## Memory and work bound

Let P=14, B=512, K_i be each pattern's instruction count, C=512 captured bytes,
L=4096 inline bytes, and E the configured maximum evidence count (default 4096).

* Source hashing is one existing `elpis_sha256_ctx`; source bytes are never
  concatenated. Each candidate has one such match context.
* The decoder has four bytes and fixed counters.
* A viable start cannot cross more than B non-whitespace scalars. Every new
  start consumes a distinct non-whitespace scalar, and no new start appears in
  an unbounded whitespace run. Completed candidates can wait only behind such
  a viable start. Consequently each pattern has at most B+1 pending candidates;
  an explicit guard enforces that bound.
* A candidate has at most K_i live threads. Closure's visited-PC set prevents
  cycles or exponential backtracking; its work stacks are O(K_i). At most five
  bounded captures are present per thread (only three are used together by the
  actual grammar).
* Inline text and one saved winner are each at most L bytes per candidate.
  Once a growing match exceeds L, its inline buffer is released; its SHA context
  continues over every original byte. Earlier saved matches retain their own
  exact bounded snapshot.
* Persistent lexical payload storage is therefore bounded by
  O(sum_i((B+1)*(K_i*5*C + 2*L + sizeof(SHA context)))). Closure scratch is
  O(max_i(K_i*5*C)). This deliberately conservative grammar bound is independent
  of source length; it is not a claim that all possible hostile states fit the
  much smaller measured steady-state examples.
* Accepted evidence storage is O(E*(L+5*C+metadata)). Canonical sorting,
  composition and result strings scale with emitted evidence and escaped output
  size, not with unrelated input. Exceeding E returns E_RANGE without a result.

The implementation uses standard containers; allocator metadata/capacity factors
are implementation-dependent. Stats report observed candidate/thread counts and
actual inline/capture string capacities. `test_v2_memory.cpp` also intercepts
**all C++ allocations**, so hidden retained source strings would fail the test
rather than escape the selected stats counters. Fixed PCRE2 allocations are not
counted by that interceptor. The test compares live and peak allocations after
1 MiB and after 50 MiB without matches, and after 1 MiB and 3 MiB of an unresolved
whitespace-spanning match. Both remain exactly unchanged. Output construction
is measured separately from the pending-source bound.

Per-scalar work is bounded by the compiled grammar and pending starts, not by
source-prefix length. ASCII runs with no viable start avoid unnecessary machine
work. Huge numbers and near-matching repeated prefixes cannot create unlimited
capture storage or PCRE2 catastrophic backtracking. There is no performance
claim independent of the number of emitted evidence records.

## C ABI and downstream boundary

`include/streaming_regex_ingress_v2.h` adds create/feed/finalize/destroy, stats and
thread-local error access. Options have an exact version/size check, zero reserved
field, a maximum evidence count and a source byte-count limit. The latter cannot
exceed UINT64_MAX/8, preserving SHA-256's 64-bit bit-length representation.
Length checks occur before dereferencing a purported oversized buffer.

NULL options choose defaults. NULL+0 feeds are no-ops while open. NULL+nonzero is
fatal; null handles/output arguments are rejected. A null finalize output slot
leaves an open stream usable. Re-finalization and feed after finalization return
E_STATE and cannot mutate the independently owned published result. Failed
streams retain their original failure code. Destroy-null is safe. Double destroy,
forged/stale pointers, invalid buffers and concurrent use of one handle are
caller UB; global pointer registries are not introduced to pretend otherwise.
Independent handles are safe concurrently. V2 error reporting uses static
thread-local strings, including allocation failures.

Finalization returns an opaque result read and destroyed through existing V1
accessors. The additive downstream function
`elpis_regex_hacf_query_ingress_from_regex_result_v2` borrows that immutable
result, constructs the existing HACF context proposal, and calls the same
query-local atomic batch path. It neither reparses source nor retains a caller's
result pointer. Corpus and immutable context graph are read-only. Semantic,
admission, execution and runtime authority stay zero; candidate status stays
PROPOSED_UNADMITTED. No ECS, persistent graph, P4, RetrievalBundle, vector,
Grid81 or runtime-admission extension is made.
