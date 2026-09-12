from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pypi-publish.yaml"


def test_trusted_publisher_identity_and_oidc_boundary():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "release:" in text
    assert "types: [published]" in text
    assert "name: pypi" in text
    assert "id-token: write" in text
    assert "pypa/gh-action-pypi-publish@release/v1" in text
    assert "python-package-distributions" in text

    forbidden = (
        "TWINE_PASSWORD",
        "PYPI_TOKEN",
        "password:",
        "secrets.",
    )
    for marker in forbidden:
        assert marker not in text


def test_publish_job_is_separate_from_build_job():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "\n  build:\n" in text
    assert "\n  publish:\n" in text
    assert "needs: build" in text
    assert "permissions: {}" in text
