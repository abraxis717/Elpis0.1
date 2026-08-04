"""Corpus compilation orchestration.

Compiles all source rows into all four typed views with orbit identities.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

from elpis_grid81_typed.canonical import canonicalize, domain_digest
from elpis_grid81_typed.d4 import verify_d4_group
from elpis_grid81_typed.source_identity import SourceRowIdentityV1
from elpis_grid81_typed.transition import T00TransitionViewV1
from elpis_grid81_typed.expansion import T00ExpansionLocusViewV1
from elpis_grid81_typed.quiescence import T00QuiescenceViewV1
from elpis_grid81_typed.rationale import T00RationaleViewV1
from elpis_grid81_typed.typed_orbits import (
    TransitionOrbitV1,
    ExpansionOrbitV1,
    QuiescenceOrbitV1,
    RationaleOrbitV1,
)
from elpis_grid81_typed.errors import (
    TransitionCompilerError,
    ExpansionCompilerError,
    QuiescenceCompilerError,
    RationaleCompilerError,
)


def load_corpus(corpus_dir: str) -> List[Tuple[Dict[str, Any], str]]:
    """Load T00 corpus rows with split labels.

    Returns list of (row_dict, split) tuples.
    """
    rows = []
    split_files = {
        "train": "train.jsonl",
        "validation": "validation.jsonl",
        "test": "test.jsonl",
    }
    for split, filename in sorted(split_files.items()):
        path = os.path.join(corpus_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Corpus file not found: {path}")
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    row = json.loads(line)
                    rows.append((row, split))
    return rows


def compile_row(
    row: Dict[str, Any],
    source_split: str,
) -> Dict[str, Any]:
    """Compile a single source row into all four typed views with orbits.

    Returns a dict containing all view results and orbit identities.
    """
    # Source identity
    identity = SourceRowIdentityV1.from_row(row, source_split)

    # Transition view
    transition = T00TransitionViewV1.compile(
        source_case_id=identity.source_case_id,
        source_row_digest=identity.source_row_digest,
        input_grid=row["input_grid"],
        input_mask=row["input_mask"],
        canonical_target_grid=row["canonical_target_grid"],
    )

    # Expansion view
    expansion = T00ExpansionLocusViewV1.compile(
        source_case_id=identity.source_case_id,
        source_row_digest=identity.source_row_digest,
        input_grid=row["input_grid"],
        stored_expansion_targets=row.get("expansion_targets"),
    )

    # Quiescence view
    quiescence = T00QuiescenceViewV1.compile(
        source_case_id=identity.source_case_id,
        source_row_digest=identity.source_row_digest,
        input_grid=row["input_grid"],
        stored_quiescence=row.get("quiescence_target", False),
    )

    # Rationale view
    rationale = T00RationaleViewV1.compile(
        source_case_id=identity.source_case_id,
        source_row_digest=identity.source_row_digest,
        input_grid=row["input_grid"],
        canonical_target_grid=row["canonical_target_grid"],
        rationale_codes=row.get("rationale_codes", []),
    )

    # Orbit identities
    transition_orbit = TransitionOrbitV1.compute(transition.to_dict())
    expansion_orbit = ExpansionOrbitV1.compute(expansion.to_dict())
    quiescence_orbit = QuiescenceOrbitV1.compute(quiescence.to_dict())
    rationale_orbit = RationaleOrbitV1.compute(rationale.to_dict())

    return {
        "identity": identity,
        "transition": transition,
        "expansion": expansion,
        "quiescence": quiescence,
        "rationale": rationale,
        "transition_orbit": transition_orbit,
        "expansion_orbit": expansion_orbit,
        "quiescence_orbit": quiescence_orbit,
        "rationale_orbit": rationale_orbit,
    }


def compile_corpus(
    corpus_dir: str,
    output_dir: str,
) -> Dict[str, Any]:
    """Compile entire T00 corpus and produce typed inventories.

    Returns compilation statistics and audit results.
    """
    rows = load_corpus(corpus_dir)
    total_rows = len(rows)

    # Statistics accumulators
    stats = {
        "total_rows": total_rows,
        "transition": {"noop": 0, "edit": 0, "rejected": 0},
        "expansion": {"compiled": 0, "mismatches": 0},
        "quiescence": {"agreed": 0, "stale": 0, "stored_true_derived_false": 0, "stored_false_derived_true": 0},
        "rationale": {"compiled": 0},
        "orbits": {
            "transition_unique": set(),
            "expansion_unique": set(),
            "quiescence_unique": set(),
            "rationale_unique": set(),
        },
        "split_counts": {
            "transition": {"train": 0, "validation": 0, "test": 0},
            "expansion": {"train": 0, "validation": 0, "test": 0},
            "quiescence": {"train": 0, "validation": 0, "test": 0},
            "rationale": {"train": 0, "validation": 0, "test": 0},
        },
        "errors": [],
    }

    # Inventories
    identity_records = []
    transition_records = []
    expansion_records = []
    quiescence_records = []
    rationale_records = []

    for idx, (row, split) in enumerate(rows):
        try:
            result = compile_row(row, split)
        except (TransitionCompilerError, ExpansionCompilerError, QuiescenceCompilerError, RationaleCompilerError) as e:
            stats["errors"].append({
                "case_id": row.get("case_id", f"unknown_{idx}"),
                "split": split,
                "error": str(e),
            })
            continue

        identity = result["identity"]
        transition = result["transition"]
        expansion = result["expansion"]
        quiescence = result["quiescence"]
        rationale = result["rationale"]
        t_orbit = result["transition_orbit"]
        e_orbit = result["expansion_orbit"]
        q_orbit = result["quiescence_orbit"]
        r_orbit = result["rationale_orbit"]

        # Transition stats
        if transition.delta_kind == "NOOP":
            stats["transition"]["noop"] += 1
        elif transition.delta_kind == "EDIT":
            stats["transition"]["edit"] += 1
        else:
            stats["transition"]["rejected"] += 1

        stats["split_counts"]["transition"][split] += 1

        # Expansion stats
        stats["expansion"]["compiled"] += 1
        stats["split_counts"]["expansion"][split] += 1

        # Quiescence stats
        if quiescence.lineage_status == "AGREED":
            stats["quiescence"]["agreed"] += 1
        else:
            stats["quiescence"]["stale"] += 1
            if quiescence.stored_quiescence and not quiescence.derived_quiescence:
                stats["quiescence"]["stored_true_derived_false"] += 1
            elif not quiescence.stored_quiescence and quiescence.derived_quiescence:
                stats["quiescence"]["stored_false_derived_true"] += 1

        stats["split_counts"]["quiescence"][split] += 1

        # Rationale stats
        stats["rationale"]["compiled"] += 1
        stats["split_counts"]["rationale"][split] += 1

        # Orbit tracking
        stats["orbits"]["transition_unique"].add(t_orbit.orbit_digest)
        stats["orbits"]["expansion_unique"].add(e_orbit.orbit_digest)
        stats["orbits"]["quiescence_unique"].add(q_orbit.orbit_digest)
        stats["orbits"]["rationale_unique"].add(r_orbit.orbit_digest)

        # Inventory records
        identity_records.append({
            **identity.to_dict(),
            "source_split": split,
        })
        transition_records.append({
            **transition.to_dict(),
            "source_split": split,
            "transition_orbit_digest": t_orbit.orbit_digest,
            "transition_orbit_size": t_orbit.orbit_size,
            "transition_stabilizer_size": t_orbit.stabilizer_size,
        })
        expansion_records.append({
            **expansion.to_dict(),
            "source_split": split,
            "expansion_orbit_digest": e_orbit.orbit_digest,
            "expansion_orbit_size": e_orbit.orbit_size,
            "expansion_stabilizer_size": e_orbit.stabilizer_size,
        })
        quiescence_records.append({
            **quiescence.to_dict(),
            "source_split": split,
            "quiescence_orbit_digest": q_orbit.orbit_digest,
            "quiescence_orbit_size": q_orbit.orbit_size,
            "quiescence_stabilizer_size": q_orbit.stabilizer_size,
        })
        rationale_records.append({
            **rationale.to_dict(),
            "source_split": split,
            "rationale_orbit_digest": r_orbit.orbit_digest,
            "rationale_orbit_size": r_orbit.orbit_size,
            "rationale_stabilizer_size": r_orbit.stabilizer_size,
        })

    # Write inventories
    os.makedirs(output_dir, exist_ok=True)

    def write_jsonl(path: str, records: list):
        with open(path, "w") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")

    write_jsonl(os.path.join(output_dir, "G40B1_SOURCE_IDENTITY_INVENTORY.jsonl"), identity_records)
    write_jsonl(os.path.join(output_dir, "G40B1_TRANSITION_INVENTORY.jsonl"), transition_records)
    write_jsonl(os.path.join(output_dir, "G40B1_EXPANSION_INVENTORY.jsonl"), expansion_records)
    write_jsonl(os.path.join(output_dir, "G40B1_QUIESCENCE_INVENTORY.jsonl"), quiescence_records)
    write_jsonl(os.path.join(output_dir, "G40B1_RATIONALE_INVENTORY.jsonl"), rationale_records)

    # Compute inventory digests
    def inventory_digest(records: list) -> str:
        combined = b"".join(
            json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            for r in records
        )
        return domain_digest("row", combined)

    # Return compilation results
    return {
        "stats": {
            **stats,
            "orbits": {
                k: len(v) for k, v in stats["orbits"].items()
            },
        },
        "inventory_digests": {
            "source_identity": inventory_digest(identity_records),
            "transition": inventory_digest(transition_records),
            "expansion": inventory_digest(expansion_records),
            "quiescence": inventory_digest(quiescence_records),
            "rationale": inventory_digest(rationale_records),
        },
        "row_counts": {
            "source": len(identity_records),
            "transition": len(transition_records),
            "expansion": len(expansion_records),
            "quiescence": len(quiescence_records),
            "rationale": len(rationale_records),
        },
        "errors": stats["errors"],
    }
