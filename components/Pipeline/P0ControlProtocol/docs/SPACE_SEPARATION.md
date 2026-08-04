# Grid81 Semantic-Space Separation

C.NumPyCortex and P0 both transport 81 values in the range 0–9, but
those values currently have different meanings.

## Space A: thermal ordinal Grid81

Produced by:

```text
CNumPyCortex
````

Meaning:

```text
0   missing or invalid telemetry
1–9 robustly normalized ordinal telemetry bins
```

A value of 6 in this space means:

```text
the sampled value fell into ordinal bin 6
```

It does not mean expansion.

## Space B: structural instruction Grid81

Produced by:

```text
P0 DeterministicPythonProjector
```

Meaning:

```text
0 VOID
1 INPUT
2 TRANSFORM
3 OUTPUT
4 MEMORY
5 CONSTRAINT
6 EXPANSION
7 ROUTE
8 INTERFACE
9 RESOLUTION
```

A value of 6 in this space means:

```text
the TRM/controller may propose decomposition
```

## Consequence

The spaces are shape-compatible but not semantically interchangeable:

[
\text{shape}(A)=\text{shape}(B)=81
]

but:

[
\llbracket A_i \rrbracket_{\mathrm{thermal}}
\neq
\llbracket B_i \rrbracket_{\mathrm{structural}}
]

Therefore:

```text
Never send thermal Grid81 tokens directly into a structural-opcode
checkpoint.

Never interpret a thermal value of 6 as BASIS_EXPANSION.

Never train a single checkpoint on both spaces without an explicit
space identifier and codec.
```

## Required future codec

A future `ThermalStructuralCodec` may map features such as:

```text
rapid rise
cross-channel thermal gradient
forecast interval violation
llama-server health transition
persistent residual
```

into structural opcodes such as:

```text
CONSTRAINT
EXPANSION
ROUTE
INTERFACE
RESOLUTION
```

That codec must be independently validated. It is not part of P0.
