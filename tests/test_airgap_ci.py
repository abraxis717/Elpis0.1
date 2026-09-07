"""Static regression for the permanent CNumPyCortex airgap CI gate."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"


def _job() -> str:
    text = CI.read_text(encoding="utf-8")
    start = text.index("  cnum-py-cortex-airgap:\n")
    end = text.index("\n  runtime-r0:\n", start)
    return text[start:end]


def test_airgap_ci_job_runs_exact_policy_regressions():
    job = _job()

    assert "components/CNumPyCortex/src" in job
    assert "components/CNumPyCortex/tests/test_airgap.py" in job
    assert "components/CNumPyCortex/tests/test_subprocess_policy.py" in job
    assert "-q -p no:cacheprovider" in job


def test_airgap_ci_job_is_push_gated_with_main_ci():
    text = CI.read_text(encoding="utf-8")

    assert "      - main" in text
    assert "      - 'ci/**'" in text
    assert text.count("  cnum-py-cortex-airgap:\n") == 1
