"""The standalone qualifier compares fresh histories, not only replay seeds."""
import importlib.util
from pathlib import Path


def test_independent_hash_seed_and_restart_histories(tmp_path):
    path = Path(__file__).resolve().parents[1] / "qualification" / "run.py"
    spec = importlib.util.spec_from_file_location("ecs_qualification", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.determinism(tmp_path)
    assert result["independent_histories"] == 20
    assert result["fresh_replays"] == 20
    assert result["all_canonical_outputs_equal"]
