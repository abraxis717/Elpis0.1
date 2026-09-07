"""Static regression for the permanent HACF sanitizer CI authority."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"


def _ci() -> str:
    return CI.read_text(encoding="utf-8")


def _sanitizer_job(text: str) -> str:
    start = text.index("  hacf-sanitizers:\n")
    end = text.index("\n  runtime-r1:\n", start)
    return text[start:end]


def test_hacf_sanitizer_job_is_present_and_bounded():
    job = _sanitizer_job(_ci())

    assert "-DELPIS_ENABLE_ASAN=ON" in job
    assert "-DELPIS_ENABLE_UBSAN=ON" in job
    assert "-DELPIS_ENABLE_TSAN=OFF" in job

    assert "libasan\\.so" in job
    assert "libubsan\\.so" in job
    assert "LD_PRELOAD=" in job

    # Native executables retain LSan.
    assert "detect_leaks=1" in job

    # CPython-hosted runs disable only LSan; ASAN/UBSAN remain fail-fast.
    assert job.count("detect_leaks=0") >= 3

    assert "runtime/R1/tests/test_r1.py::TestHacfRetrieval" in job
    assert "runtime/R1/tests/test_r1.py" in job


def test_sanitizer_job_is_additive_to_plain_native_gates():
    text = _ci()

    assert "  hacf-native:" in text
    assert "  hacf-wrapper:" in text
    assert "  hacf-sanitizers:" in text


def test_python_boundary_never_disables_asan_or_ubsan():
    job = _sanitizer_job(_ci())

    assert "halt_on_error=1" in job
    assert "abort_on_error=1" in job
    assert "UBSAN_OPTIONS: halt_on_error=1:print_stacktrace=1" in job
    assert "ASAN_OPTIONS: detect_leaks=0" not in job
