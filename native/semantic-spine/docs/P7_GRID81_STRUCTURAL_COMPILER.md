# P7 — Grid81 Structural Compiler

## Overview

P7 is a deterministic structural compiler that transforms P6 semantic-topology
IR into a valid Grid81 structural packet. It is purely structural: no TRM
execution, no StructuralOracle, no learned projector, no residual81, no
runtime admission.

## Pipeline Position

```
P5 bounded semantic view
  -> P6 semantic-topology IR
  -> P6 SEMANTIC_TO_GRID81_COMPILER_INPUT handoff
  -> P7 topology capsules
  -> deterministic Grid81 cell placement
  -> canonical partial Sudoku digits
  -> Grid81 [81][10] digit-class tensor
  -> P7 structural packet and trace sidecar
  -> future P8 TRM adapter and writable-mask qualification
```

## Architecture

### Source Layout

Headers: `include/elpis_semantic/grid81_*.h`
Sources: `src/grid81/grid81_*.c`
Tests: `tests/grid81/test_grid81_compiler.c`

### Modules

| Module | Purpose |
|--------|---------|
| grid81_policy | Immutable compiler policy (cell count, capacities, behavioral rules) |
| grid81_codebook | Fixed lane-to-column mapping (10 lanes, 9 columns) |
| grid81_capsule | Topology capsule definition and key comparison |
| grid81_place | Deterministic cell placement (row/col formulas) |
| grid81_sudoku_template | Canonical Sudoku template and partial-board validation |
| grid81_cell | Cell records, occupied/writable masks |
| grid81_constraint_projection | Constraint projection dispositions |
| grid81_packet | Structural packet assembly and validation |
| grid81_compile_receipt | Compilation receipt with verification counters |
| grid81_handoff | P8 TRM adapter handoff ABI |
| grid81_persist | Serialization helpers, tensor construction |

### Grid81 Contract

- 81 cells, row-major (cell = row * 9 + column)
- Digits 0-9 (0 = empty, 1-9 = Sudoku clue digit)
- 10 digit classes per cell, binary one-hot representation
- Compiler writable mask: all zero
- Occupied mask: 1 when digit > 0, 0 otherwise

### Placement

Column determined by P6 primary lane through fixed codebook.
Row = (primary_constellation_index + semantic_stratum) mod 9.
Cell = row * 9 + column.

### Sudoku Template

Canonical solved board: digit(r,c) = 1 + ((r*3 + r/3 + c) % 9)
Partial board: nonzero cells must match canonical template exactly.

### Authority Boundaries

P6 owns: vertices, incidences, anchors, distances, constellations,
affiliations, roles, lanes, conflicts, bridges, metric hints, addresses,
constraints, semantic authority, relation identity.

P7 owns: capsule construction, Grid81 placement, Sudoku digit assignment,
occupied-cell representation, one-hot digit representation, trace manifests,
constraint-projection classification, structural-packet construction.

## Qualification

- 74/74 P7 tests passing
- 55/55 P0-P6 semantic fabric tests passing (no regressions)
- ASan + UBSan clean
- All evidence artifacts in reports/P7Grid81StructuralCompiler/

## Next Action

SEMANTIC_HYPERGRAPH_P8_TRM_ADAPTER_AND_MUTABILITY_POLICY
