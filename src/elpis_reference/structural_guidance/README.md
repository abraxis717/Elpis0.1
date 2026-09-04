# Structural Guidance Runtime

This package productionizes the sealed:

C2R6-P0 Projector
→ C2R6-P1 structural-refiner ABI
→ frozen C2R7-C objective
→ frozen TRM0 equal-best ordering guidance
→ C2R6-P1 transition validation/replay

runtime boundary.

The structural-guidance component itself is admitted.

The request-level gate defaults OFF.

The semantic binding envelope remains outside the model input.

TRM authority is always zero.

Candidate legality and transition execution remain C2R6-P1-owned.

The deterministic objective remains the frozen C2R7-C objective.

TRM0 may affect stable ordering before the strict-improvement scan and
therefore may change the selected action only among equal-best improving
candidates.

Plateau escape remains unguided.

Static residual-family pruning remains disabled.

The checkpoint path is supplied by the host but the admissible checkpoint
SHA-256 is hard-pinned in the production package.

Failure does not execute an alternate path implicitly. It returns
FALLBACK_REQUIRED so the enclosing controller retains explicit fallback
authority.

This bounded component admission does not imply full Elpis runtime
admission. Repository-wide governance, serving, persistent authority, and
generalized semantic runtime admission remain false.

The live Projector caller hook is intentionally a separate gate and remains
inactive until qualified.
