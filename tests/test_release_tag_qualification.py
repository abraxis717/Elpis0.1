"""Supported release tags must enter every public qualification workflow."""
import ast
import fnmatch
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

QUALIFICATION_WORKFLOWS = (
    ".github/workflows/ci.yml",
    ".github/workflows/reference-runtime.yml",
    ".github/workflows/platform-matrix.yml",
)

SUPPORTED_TAGS = (
    "v0.0.0",
    "Elpis0.0.0",
)


def _push_tag_patterns(path: str) -> tuple[str, ...]:
    workflow = (ROOT / path).read_text(encoding="utf-8")

    try:
        push = workflow.split(
            "  push:\n",
            1,
        )[1].split(
            "  pull_request:",
            1,
        )[0]
    except IndexError as exc:
        raise AssertionError(
            f"{path}: canonical push block not found"
        ) from exc

    match = re.search(
        r"^    tags: (\[.*\])$",
        push,
        re.MULTILINE,
    )

    assert match is not None, (
        f"{path}: release-tag qualification absent"
    )

    patterns = ast.literal_eval(match.group(1))

    assert isinstance(patterns, list)
    assert all(
        isinstance(pattern, str)
        for pattern in patterns
    )

    return tuple(patterns)


def test_supported_release_tags_enter_all_qualification_workflows():
    current = (
        "Elpis"
        + (ROOT / "VERSION").read_text(
            encoding="utf-8"
        ).strip()
    )

    historical = tuple(
        path.stem
        for path in (ROOT / "RELEASE_NOTES").glob(
            "Elpis*.md"
        )
    )

    tags = (
        *SUPPORTED_TAGS,
        current,
        *historical,
    )

    for workflow in QUALIFICATION_WORKFLOWS:
        patterns = _push_tag_patterns(workflow)

        for tag in tags:
            assert any(
                fnmatch.fnmatchcase(
                    tag,
                    pattern,
                )
                for pattern in patterns
            ), (
                f"{workflow}: "
                f"release tag {tag!r} is unqualified"
            )


def test_ci_release_verifier_remains_bound():
    workflow = (
        ROOT / ".github/workflows/ci.yml"
    ).read_text(encoding="utf-8")

    assert (
        "python tools/verify_public_release.py"
        in workflow
    )

    assert (
        "tests/test_release_tag_qualification.py"
        in workflow
    )
