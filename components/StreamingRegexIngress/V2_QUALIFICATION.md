# V2 successor qualification — 2026-09-12

## Starting authority and scope

* Checkout: canonical Astra Elpis0.1, branch `main`, initially clean.
* HEAD and origin/main: `0d64119896951aa1815a127b28b7b5a5989fab75`.
* Underlying release: `Elpis2.1.23`, release commit
  `5a2ecfe91a330ef30889f816a8c018eb8828d1aa`.
* Implementation and tests were performed directly in this checkout, without
  Git metadata writes, worktrees, commits, tags, pushes or publication.
* All build/oracle/runtime fixture state was under `.v2-build`, `.v2-release`,
  or `.v2-sanitize` inside the checkout. Generated state and logs were removed
  after qualification; this report retains commands and exact outcomes.
* ECS, historical release manifests, frozen authority material and publication
  registry were not modified.

Environment: GCC/G++ 16.1.1, CMake 4.3.3, PCRE2 10.47, C++17. No dependencies were
installed. The native library and downstream library compile with
`-Wall -Wextra -Wpedantic -Werror`.

The implementation decision, grammar census, byte-partition proof and memory
bound are in [V2_DESIGN.md](V2_DESIGN.md). V2 is working incremental code, with an
explicit long-match representation boundary. It is **not** a claim of full
V1 canonical JSON identity for arbitrarily large matches.

## Pre-edit baseline

Commands from repository root:

```sh
cmake -S . -B .v2-build -DCMAKE_BUILD_TYPE=Debug
cmake --build .v2-build -j 4
ctest --test-dir .v2-build --output-on-failure
.v2-build/components/StreamingRegexIngress/elpis_streaming_regex_b01_regression
.v2-build/components/StreamingRegexIngress/elpis_streaming_regex_b01_cli_io_regression
.v2-build/components/RegexHACFQueryIngress/elpis_regex_hacf_b01_regression .v2-build/baseline-corpus
```

Build: PASS. Root CTest: **88 passed, 8 failed, 96 total** (13.57 seconds).
Failures were `segment_snapshot`, `embedding_storage`, `context_persistence`,
`evidence_persistence`, `p5_persistence`, `topology_compile`, `grid81_compiler`,
and `p13_structural_spine`. These existing tests use fixed persistence paths
outside the writable repository, including `/tmp`. `context_persistence`
segfaulted after failed write/read operations. These are baseline/environment
failures, not V2 regressions. They were excluded from the final root run so those
outside-repository fixture operations would not be repeated.

The existing Regex tests were not registered with root CTest before this change.
All three directly executed baseline targets passed:

* `PASS_STREAMING_REGEX_B01_BOUNDED_PROFILE_R1`
* `PASS_STREAMING_REGEX_B01_CLI_EOF_GATE_R2`
* `PASS_REGEX_HACF_B01_PREPUBLICATION_R1`

## Historical oracle scope

The repository carries the historical 28-valid/3-invalid, 196/21-run matrix's
hash bindings in `contracts/PARITY_BINDING.json`, and historical downstream
identity bindings in `RegexHACFQueryIngress/contracts/COMPOSITION_BINDING_V1.json`.
It does not carry the original fixture inputs or Python oracle as an executable
matrix. Current tracked paths, the introducing component/ABI commits, and the
reachable Git object-path census were inspected; the matrix was not recovered.
Digest declarations are not substitute fixtures. The exact historical 196/21
matrix is therefore **not reported as rerun**.

An independent executable regression oracle was built from the exact starting
HEAD source, rather than using only the refactored V1 code as the oracle:

```sh
git show HEAD:components/StreamingRegexIngress/src/native_regex_ingress.cpp > .v2-build/frozen_v1.cpp
cc -fPIC -c native/hacf/src/hash/sha256.c -I native/hacf/include -o .v2-build/frozen_sha.o
c++ -O2 -shared -fPIC -std=c++17 -DELPIS_STREAMING_REGEX_NO_MAIN=1 \
  .v2-build/frozen_v1.cpp .v2-build/frozen_sha.o \
  -I components/StreamingRegexIngress/include \
  -I components/StreamingRegexIngress/src -I native/hacf/include \
  -lpcre2-8 -o .v2-build/frozen_v1.so
.v2-release/components/StreamingRegexIngress/elpis_streaming_regex_v2_test "$PWD/.v2-build/frozen_v1.so"
```

Result: **3,024 parity runs passed**, with 75 named successor fixtures, every
byte split, fixed 1/2/7/13/whole feed profiles, seeded partitions/compositions and
malformed input. Current V1 acceptance and complete canonical JSON matched the
frozen-HEAD oracle. V2 matched V1 in its common exact-text domain. The comparisons
include separate source/count, evidence, pattern/anchor/ID, candidate ID,
ambiguity, disposition, ingress and composition accessors.

The unchanged public V1 header and qualified carry-1/carry/carry+1 regressions
remain intact. Exact pre-edit/post-edit downstream B01 output compared equal
with `diff -u`, including all proposal, candidate, overlay and receipt identities.

## Final root and subsystem qualification

```sh
cmake -S . -B .v2-release -DCMAKE_BUILD_TYPE=Release
cmake --build .v2-release -j 4
ctest --test-dir .v2-release --output-on-failure \
  -E '^(segment_snapshot|embedding_storage|context_persistence|evidence_persistence|p5_persistence|topology_compile|grid81_compiler|p13_structural_spine)$'
```

**97 passed, zero failed** (38.93 seconds); eight known path-incompatible baseline
tests excluded. Root build passed with the changed native targets' warnings as
errors. All nine Regex-related CTests passed:

| Test | Coverage |
| --- | --- |
| streaming_regex_v1_bounded | Frozen V1 carry/range, contradiction and UTF-8 regressions |
| streaming_regex_v1_cli_eof | Existing CLI EOF/read-failure gate |
| streaming_regex_v2 | 3,024 differential runs; lifecycle; UTF-8; long source and whitespace |
| streaming_regex_v2_allocation | Deterministic C++ allocation failures during create/feed/finalize |
| streaming_regex_v2_c_abi | C compilation/linkage, empty input, independent result lifetime |
| streaming_regex_v2_memory | All-C++-allocation growth interception and absolute measured bounds |
| streaming_regex_v2_properties | 963 deterministic property runs; 14 long pattern families |
| regex_hacf_v1_bounded | Existing V1 prepublication and whole-chain identity regression |
| regex_hacf_v2 | Finalized-result consumption, identity parity, long-source ambiguity, authority zero |

The Python property suite ran with `PYTHONDONTWRITEBYTECODE=1`; it has no package
dependencies and is a test-only CMake option when a Python interpreter exists.
It tests 4,095/4,096/4,097/16,384-byte match boundaries, exact long-match hash and
offsets, all 14 families with long mixed whitespace, 2 MiB sparse-source exact
V1 parity, 300 seeded Unicode/byte mutations under three partitions, and long
near-prefix/number/repeated-partial inputs. Its long-match oracle removes only
the documented inline field, updates the schema/omission marker, and independently
recomputes the evidence ID. All remaining canonical bytes must match.

The existing QueryLocalProposalIngress `test_atomic_batch.c` was also compiled
against the root-built real native support and executed unchanged:

```sh
cc -std=c11 -I components/QueryLocalProposalIngress/include \
  -I native/semantic-spine/include -I native/hacf/include \
  components/QueryLocalProposalIngress/tests/test_atomic_batch.c \
  .v2-release/components/RegexHACFQueryIngress/libelpis_regex_hacf_query_ingress.a \
  .v2-release/native/hacf/libelpis_hash.a -lstdc++ -lpthread \
  -o .v2-release/qlp_atomic_test
.v2-release/qlp_atomic_test
```

Result: `PASS_ATOMIC_QUERY_LOCAL_PROPOSAL_BATCH_INGRESS_R1`. Existing proposal-set,
overlay and batch-receipt identities matched its committed fixture. Invalid
second envelopes, invalid authority, duplicate proposals, wrong context, zero
count and over-bound cases all passed atomic-failure controls.

## Long-stream and memory observations

Native qualification generated source from reusable blocks. It processed:

* 52,428,800 bytes with no matches, followed by distant/late evidence;
* the same greater-than-50-MiB source in one caller-owned feed, with complete
  result/accessor equality against segmented ingestion;
* 2,359,305 bytes in one match with mixed whitespace, with an independently
  computed exact match SHA-256;
* hostile partitions of every lexical family and repeated identical evidence
  at different absolute offsets;
* malformed UTF-8 after a 2 MiB valid prefix, with no published result;
* 2.5 MiB sources through Regex → HACF → query-local proposals, including
  contradictory evidence rejected before batch publication.

Lexical stats for the 50 MiB no-match run: peak 2 pending candidates, 254 threads,
510 inline-capacity bytes, 25,114 capture-capacity bytes. For the long whitespace
match: peak 7 candidates, 258 threads, 30,780 inline-capacity bytes, 19,800
capture-capacity bytes. These are aggregate string capacities, not the inline
text limit of a single match.

A separate test intercepts all C++ allocations (including its fixed 128 KiB
caller buffers and the shared grammar's C++ state):

| Stream | Bytes processed | Live after 1 MiB | Live at end | Peak |
| --- | ---: | ---: | ---: | ---: |
| No match | 52,428,800 | 303,050 | 303,050 | 424,996 |
| Pending whitespace match | 3,145,728 | 346,394 | 346,394 | 400,194 |

Both live allocation and high-water allocation remain exactly flat after the
first MiB. A hidden source-concatenation buffer would fail these checks. Fixed
PCRE2 C allocations are excluded from the interceptor; they do not grow with
source length. These measurements are not a universal worst-case RSS claim.
The grammar-dependent bound and emitted-evidence/output distinction are proved
separately in the design notes.

## Sanitizers

The changed shared library, downstream composition and native tests were all
instrumented via root C/C++ flags (not only the HACF subdirectory option):

```sh
cmake -S . -B .v2-sanitize -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  '-DCMAKE_C_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer' \
  '-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer'
cmake --build .v2-sanitize -j 4 --target \
  elpis_streaming_regex_v2_test elpis_streaming_regex_v2_allocation \
  elpis_streaming_regex_v2_memory elpis_streaming_regex_v2_c_abi \
  elpis_streaming_regex_b01_regression elpis_streaming_regex_b01_cli_io_regression \
  elpis_regex_hacf_v2_test elpis_regex_hacf_b01_regression
ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 \
  ctest --test-dir .v2-sanitize -R 'streaming_regex|regex_hacf' \
  -E properties --output-on-failure
```

**8/8 passed** (296.19 seconds), with no ASAN or UBSAN findings. The Python ctypes
property driver was qualified in the ordinary build; sanitizer coverage used
the native executables.

An initial attempt with leak detection enabled failed because LeakSanitizer
reported that it cannot operate under the sandbox's ptrace setup. That mechanics
failure is not called a code defect or a sanitizer pass. LeakSanitizer remains
unqualified in this environment. C++ failure injection observed 12 create,
11 feed and 11 finalize allocation-failure cases, all returning E_NOMEM without
publishing a result; failed streams remained terminal.

## Remaining limitations and review boundary

* Exact V1 canonical evidence for unbounded matched text is mathematically
  incompatible with bounded pending storage. V2 uses an explicit schema change
  only for matches over 4,096 bytes. No full overlap-domain identity claim is made.
* The historical 196/21 fixture matrix was not recovered; successor fixtures and
  a frozen-HEAD native oracle are reported honestly as distinct evidence.
* LeakSanitizer cannot run in this sandbox; ASAN/UBSAN passed separately.
* The eight pre-existing path-incompatible root tests remain unresolved.
* Allocation injection covers C++ allocations; PCRE2 allocation failures are
  checked and mapped but its C allocator was not exhaustively fault-injected.
* The state-machine proof applies to this frozen grammar, with the linked
  PCRE2's Unicode predicate semantics. It is not a general regex-engine claim.
* Double destroy/forged handles and concurrent mutation of one handle are caller
  UB. Independent handles use separate state and thread-local errors.

`git diff --check` passed. The recommended eventual commit boundary is the
additive V2 engine, explicit bounded-inline evidence contract, finalized-result
composition entry point and their tests/documentation together. It should not
be described as restoring the unavailable historical qualification or meeting
an impossible universal V1 matched-text identity guarantee. No commit was made.

## Final source inventory and Git state

Ten tracked files were modified and thirteen source/test/documentation files were added.
The status below is the complete file inventory. Build/cache/log artifacts from this
pass were removed. Git metadata was not changed. The ordinary diff stat excludes
untracked additions because nothing was staged.

`git diff --stat`:

```text
 components/RegexHACFQueryIngress/CMakeLists.txt    |  11 ++
 .../RegexHACFQueryIngress/COMPONENT_MANIFEST.json  |  11 ++
 .../QUALIFICATION_BINDING.json                     |  11 ++
 components/RegexHACFQueryIngress/README.md         |  14 ++
 .../src/regex_hacf_query_ingress.cpp               | 109 +++++++-----
 components/StreamingRegexIngress/CMakeLists.txt    |  34 ++++
 .../StreamingRegexIngress/COMPONENT_MANIFEST.json  |  11 ++
 .../QUALIFICATION_BINDING.json                     |  11 ++
 components/StreamingRegexIngress/README.md         |  17 ++
 .../src/native_regex_ingress.cpp                   | 196 ++++++++++++++++-----
 10 files changed, 337 insertions(+), 88 deletions(-)
```

`git status --short`:

```text
 M components/RegexHACFQueryIngress/CMakeLists.txt
 M components/RegexHACFQueryIngress/COMPONENT_MANIFEST.json
 M components/RegexHACFQueryIngress/QUALIFICATION_BINDING.json
 M components/RegexHACFQueryIngress/README.md
 M components/RegexHACFQueryIngress/src/regex_hacf_query_ingress.cpp
 M components/StreamingRegexIngress/CMakeLists.txt
 M components/StreamingRegexIngress/COMPONENT_MANIFEST.json
 M components/StreamingRegexIngress/QUALIFICATION_BINDING.json
 M components/StreamingRegexIngress/README.md
 M components/StreamingRegexIngress/src/native_regex_ingress.cpp
?? components/RegexHACFQueryIngress/include/regex_hacf_query_ingress_v2.h
?? components/RegexHACFQueryIngress/tests/test_v2_composition.cpp
?? components/StreamingRegexIngress/V2_DESIGN.md
?? components/StreamingRegexIngress/V2_QUALIFICATION.md
?? components/StreamingRegexIngress/contracts/INCREMENTAL_V2.json
?? components/StreamingRegexIngress/include/streaming_regex_ingress_v2.h
?? components/StreamingRegexIngress/src/incremental_lexer.cpp
?? components/StreamingRegexIngress/src/incremental_lexer.h
?? components/StreamingRegexIngress/tests/test_v2_allocation.cpp
?? components/StreamingRegexIngress/tests/test_v2_c_abi.c
?? components/StreamingRegexIngress/tests/test_v2_memory.cpp
?? components/StreamingRegexIngress/tests/test_v2_properties.py
?? components/StreamingRegexIngress/tests/test_v2_stream.cpp
```
