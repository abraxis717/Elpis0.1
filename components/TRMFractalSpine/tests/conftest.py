"""Pytest configuration for ModelRecursionStack.

Provides session-scoped fixtures for the deterministic corpus so that
generation runs at most once per test session.
"""
from __future__ import annotations

from typing import Tuple

import pytest

from elpis_fractal_spine.corpus_generator import CorpusGenerator
from elpis_fractal_spine.corpus_schema import CorpusCase


@pytest.fixture(scope="session")
def seed42_corpus() -> Tuple[CorpusCase, ...]:
    """Generate the full seed-42 corpus exactly once per test session.

    Returns an immutable tuple so consumers cannot mutate shared state.
    """
    gen = CorpusGenerator(seed=42)
    cases = gen.generate_all()
    return tuple(cases)
