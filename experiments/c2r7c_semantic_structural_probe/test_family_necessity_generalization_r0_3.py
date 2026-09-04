from __future__ import annotations

import json
from pathlib import Path

import family_necessity_generalization_r0_3 as h


def prereg():
    p = Path(__file__).with_name(
        "PREREGISTRATION_R0_3.json"
    )
    return json.loads(p.read_text())


def test_dev_population_exact():
    assert h.population_spec(
        prereg(),
        "dev",
    ) == {
        "base_seed": 562386460,
        "cases": 32,
        "seed_count": 8,
        "budget": 128,
    }


def test_final_population_exact():
    assert h.population_spec(
        prereg(),
        "final",
    ) == {
        "base_seed": 444400639,
        "cases": 128,
        "seed_count": 8,
        "budget": 128,
    }


def test_final_is_explicitly_gated():
    assert h.final_open_allowed(
        "dev",
        False,
    )
    assert not h.final_open_allowed(
        "final",
        False,
    )
    assert h.final_open_allowed(
        "final",
        True,
    )


def test_arm_surface_exact():
    assert len(h.ARMS) == 12
    assert h.ARMS[0] == "plain_search"
    assert h.ARMS[1] == "matched"

    for family in h.FAMILIES:
        assert (
            f"ablate_{family}"
            in h.ARMS
        )
        assert (
            f"count_control_{family}"
            in h.ARMS
        )


def test_guided_arm_parser_exact():
    assert h.parse_guided_arm(
        "matched"
    ) == ("matched", None)

    for family in h.FAMILIES:
        assert h.parse_guided_arm(
            f"ablate_{family}"
        ) == ("family", family)

        assert h.parse_guided_arm(
            f"count_control_{family}"
        ) == ("count_control", family)
