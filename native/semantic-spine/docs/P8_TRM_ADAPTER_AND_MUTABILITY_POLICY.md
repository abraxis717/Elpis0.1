# P8 — Frozen TRM Adapter and Mutability Policy

## Overview

P8 implements the deterministic boundary between the sealed P7 Grid81 structural packet and the frozen TRM execution ABI. It produces an immutable adapter packet, derives fixed/writable cell masks, and defines the output guard that protects fixed cells from TRM candidate mutations.

P8 does NOT execute the TRM, load weights, or perform recursion.

## Architecture

```
P7 Grid81 structural packet
├── grid81_digits[81]
├── grid81_digit_classes[81][10]
├── occupied_mask81
├── compiler_writable_mask81 = all zero
└── semantic trace sidecar
    ↓
P8 strict input validation
    ↓
Canonical TRM tensor [1,81,10] + P8-derived fixed/writable masks
    ↓
Immutable TRM adapter packet
    ↓
Future P9 frozen TRM execution
    ↓
TRM candidate-output frame
    ↓
P8 deterministic decoder and mutability guard
    ↓
Atomic Sudoku-validity gate
    ↓
Guarded structural result
```

## Modules

| Module | Header | Source | Purpose |
|--------|--------|--------|---------|
| TRM ABI | `trm_abi.h` | `trm_abi.c` | Frozen TRM ABI descriptor v1 |
| Adapter Policy | `trm_adapter_policy.h` | `trm_adapter_policy.c` | Immutable adapter behavioral rules |
| Input Validation | `trm_input_validate.h` | `trm_input_validate.c` | P7 handoff and structural packet validation |
| Mutability | `trm_mutability.h` | `trm_mutability.c` | Fixed/writable mask derivation |
| Input Tensor | `trm_input_tensor.h` | `trm_input_tensor.c` | Canonical [1,81,10] float32 tensor |
| Adapter Packet | `trm_adapter_packet.h` | `trm_adapter_packet.c` | Sealed adapter artifact |
| Candidate Frame | `trm_candidate_frame.h` | `trm_candidate_frame.c` | TRM candidate-output frame ABI |
| Candidate Decode | `trm_candidate_decode.h` | `trm_candidate_decode.c` | Deterministic argmax decoder |
| Output Guard | `trm_output_guard.h` | `trm_output_guard.c` | Fail-closed mutability guard |
| Guarded Result | `trm_guarded_result.h` | `trm_guarded_result.c` | Atomic guarded result packet |
| Execution Handoff | `trm_execution_handoff.h` | `trm_execution_handoff.c` | P9 execution boundary declaration |
| Persistence | `trm_persist.h` | `trm_persist.c` | SHA-256 digests, binary I/O |

## Authority Boundaries

### P7 retains authority over:
- Grid81 dimensions, row-major ordering, digit values
- Digit-class representation, occupied-cell mask
- Compiler writable mask (boundary attestation)
- Semantic sidecar, topology traceability, semantic authority

### P8 owns only:
- TRM ABI adaptation
- Model-input tensor serialization
- Fixed-cell mask derivation
- Writable-cell mask derivation
- Candidate-output schema
- Deterministic candidate decoding
- Fixed-cell restoration and writable-cell application
- Atomic Sudoku validation
- Adapter and guard receipts

### P8 must NOT:
- Reinterpret semantic relations
- Include semantic payloads in model input
- Change occupied or nonzero P7 cells
- Modify the P7 packet
- Execute a model or solver
- Define recursion termination

## Mutability Policy

```
fixed_mask81[i] = 1 when grid81_digits[i] != 0 || occupied_mask81[i] == 1
writable_mask81[i] = 1 when grid81_digits[i] == 0 && occupied_mask81[i] == 0
```

Invariant: `fixed_mask81[i] + writable_mask81[i] == 1` for all i.

## Output Guard Rules

For each cell i:
- If `fixed_mask81[i] == 1`: guarded = input digit (candidate ignored)
- If `writable_mask81[i] == 1` and `candidate == 0`: guarded = input digit (no-change)
- If `writable_mask81[i] == 1` and `candidate in 1..9`: guarded = candidate digit

Sudoku validation is atomic: all valid or complete no-op.

## Test Coverage

162 tests covering:
- TRM ABI (36 tests)
- Adapter policy (24 tests)
- P7 input validation (6 tests)
- Mutability (12 tests)
- Input tensor (11 tests)
- Sidecar isolation (4 tests)
- Adapter packet (7 tests)
- Candidate frame (9 tests)
- Candidate decoder (12 tests)
- Output guard (12 tests)
- Atomic Sudoku gate (9 tests)
- Execution handoff (19 tests)

All tests pass under ASan + UBSan.

## Evidence

Reports: `reports/P8TRMAdapterMutability/`
