from __future__ import annotations

from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"


def _readme() -> str:
    return README.read_text(encoding="utf-8")


def test_readme_keeps_single_canonical_release_declaration():
    text = _readme()
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    matches = re.findall(r"(?m)^\*\*Release line: Elpis([0-9]+\.[0-9]+\.[0-9]+)\*\*[ \t]*$", text)
    assert matches == [version]


def test_distribution_metadata_binds_markdown_readme():
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    assert project["name"] == "elpisai"
    assert project["readme"] == "README.md"
    assert project["scripts"]["elpis"] == "elpis_reference.cli:main"
    assert project["urls"] == {
        "Homepage": "https://github.com/abraxis717/Elpis",
        "Repository": "https://github.com/abraxis717/Elpis",
        "Issues": "https://github.com/abraxis717/Elpis/issues",
        "Changelog": "https://github.com/abraxis717/Elpis/blob/main/CHANGELOG.md",
    }


def test_base_dependency_contract_does_not_reintroduce_hard_torch():
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    base = tuple(project["dependencies"])
    trm = tuple(project["optional-dependencies"]["trm"])
    assert any(dep.startswith("numpy") for dep in base)
    assert any(dep.startswith("scipy") for dep in base)
    assert not any(dep.split("<", 1)[0].split(">", 1)[0].split("=", 1)[0].strip().lower() == "torch" for dep in base)
    assert any(dep.startswith("torch") for dep in trm)


def test_readme_documents_distribution_and_install_boundary():
    text = _readme()
    assert "Python distribution project name is **`elpisai`**" in text
    assert "python -m pip install elpisai" in text
    assert 'python -m pip install "elpisai[trm]"' in text
    assert "Do **not** use `pip install elpis`" in text
    assert "console command remains **`elpis`**" in text


def test_readme_removes_known_stale_frontier_claims():
    text = _readme()
    forbidden = (
        "highest-priority scientific engineering target is a C2R6-P0 allocator repair",
        "outstanding cross-process identity blocker",
        "The current package has a hard `torch` dependency",
    )
    for phrase in forbidden:
        assert phrase not in text


def test_readme_covers_post_paper_r0_public_surfaces():
    text = _readme()
    required = (
        "Authority-Preserving Improvement Witness R0",
        "27 -> 54 -> 81/81",
        "MICROSCOPIC_COLUMN_PARTICIPATION_MASK_R0",
        "SEMANTIC_IR_INSUFFICIENT",
        "AUTHORITY_ROOT_REQUIRED",
        "StreamingRegexIngress",
        "RegexHACFQueryIngress",
        "QueryLocalProposalIngress",
        "PUBLIC_COMPONENT_REGISTRY.json",
        "CNumPyCortex",
        "runtime/R0/",
        "runtime/R1/",
        "native/semantic-spine/",
        "Grid81DeterministicCapabilityAuthorityEvaluator",
        "Grid81DeterministicCapabilityConsumptionCompiler",
        "Grid81DeterministicCapabilityApplicationExecutor",
        "Grid81DeterministicCanonicalPromotionPlanner",
    )
    for marker in required:
        assert marker in text


def test_readme_preserves_critical_negative_boundaries():
    text = _readme()
    required = (
        "Repository coexistence does not imply runtime integration.",
        "The released **Elpis2.1.16** public runtime boundary remains read-only",
        "Canonical publication remains an explicitly authorized transaction.",
        "E1 and E2 have not executed.",
        "Generated source does not execute.",
        "No generated source is executed by this path.",
        "runtime admission merely because a component appears in the repository",
        "AGI or ASI",
    )
    for marker in required:
        assert marker in text


def test_readme_distinguishes_successor_writer_chain_from_public_registry():
    text = _readme()
    required = (
        "Post-2.1.16 canonical-writer engineering successor",
        "Grid81DeterministicCanonicalPromotionAuthority",
        "Grid81DeterministicCanonicalCandidateConstructor",
        "Grid81DeterministicCanonicalPublisher",
        "not yet entries",
        "ATOMIC_GRID81_CANONICAL_PROMOTION",
        "durable publication-ledger reservation",
    )
    for marker in required:
        assert marker in text

    assert "There is **no qualified in-repository writer**" not in text
