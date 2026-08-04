# G5.0B — Structural Group Projection Compiler

## Mission

Deterministic compiler converting sealed G4.0B.1 typed projections into G5.0A structural-group artifacts:
- StructuralGroupEvidenceV1 (40,960 records)
- StructuralGroupProposalV1 (40,960 records)
- ProposalOrderingV1 (8,192 records)
- StructuralConflictEvidenceV1 (derived from corpus)

## Authority Boundary

G5.0B compiles evidence and proposals only. G5.0B does not adjudicate. G5.0B does not select. G5.0B does not activate.

## Execution

    PYTHONPATH=src /path/to/python g50b_execute.py --all

## Verification

    PYTHONPATH=src /path/to/python verify_g50b.py --all

## Tests

    PYTHONPATH=src /path/to/python -m pytest tests -q
