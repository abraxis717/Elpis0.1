from __future__ import annotations

import json
from pathlib import Path

import guided_search_generalization_r0_2 as h


def _prereg():
    # Tracked archival mirror of the preregistration that was frozen
    # before R0.2 development/final execution. Its content SHA-256 is
    # identical to the original evidence copy under work/.
    p = Path(__file__).with_name("PREREGISTRATION_R0_2.json")
    return json.loads(p.read_text())


def test_dev_population_is_exactly_preregistered():
    spec = h.population_spec(_prereg(), "dev")
    assert spec == {
        "base_seed": 227919084,
        "cases": 128,
        "seed_count": 8,
        "budget": 128,
    }


def test_final_population_is_exactly_preregistered():
    spec = h.population_spec(_prereg(), "final")
    assert spec == {
        "base_seed": 712394309,
        "cases": 128,
        "seed_count": 8,
        "budget": 128,
    }


def test_final_requires_explicit_open_gate():
    assert h.final_open_allowed("dev", False)
    assert not h.final_open_allowed("final", False)
    assert h.final_open_allowed("final", True)


def test_arm_contract_is_exact():
    assert h.ARMS == (
        "plain_search",
        "search_trm_matched",
        "search_trm_zero_residual",
        "search_trm_mismatched_residual",
    )
