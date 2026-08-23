# TRM Reference Reproduction

## Purpose

Elpis will maintain a clean reference lane for the upstream Tiny Recursive Models architecture before attempting another Elpis-specific learned structural proposer.

The reference lane exists to answer one question first:

**Can the pinned upstream architecture and our training harness reproduce the documented Sudoku-Extreme capability?**

No Elpis-specific structural adaptation is admitted until that baseline is independently demonstrated.

## Upstream pin

Repository:

`SamsungSAILMontreal/TinyRecursiveModels`

Pinned commit:

`c01103738605ba39d1430519b1ee0c62f4c707f8`

The upstream repository is archived/read-only.

## Reference task

Sudoku-Extreme.

The upstream documented MLP-T configuration uses, among other settings:

- 50,000 epochs
- `arch=trm`
- `arch.mlp_t=True`
- no positional encodings
- `L_layers=2`
- `H_cycles=3`
- `L_cycles=6`
- EMA enabled

The upstream README reports an expected exact-grid accuracy of approximately 87 percent, plus or minus 2 percent.

## Qualification rule

Training and validation must exercise the same semantic task.

A clean input must never be substituted for the corrupted or incomplete puzzle during validation merely because the target answer is clean.

At minimum, qualification must report:

- puzzle-level exact-grid accuracy
- cell accuracy
- solved/unsolved counts
- fresh-process deterministic evaluation
- immutable dataset identity
- immutable model/checkpoint identity
- training configuration identity
- independent evaluation code path

## Elpis transfer rule

Only after the Sudoku reference lane passes may an Elpis-specific structural task be introduced.

The first Elpis transfer experiment must preserve the reference model and reference benchmark unchanged so that architecture capability and task-transfer effects remain separable.
