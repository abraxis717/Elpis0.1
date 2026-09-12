from pathlib import Path
import re
ROOT = Path(__file__).resolve().parents[1]

def test_root_release_note_clutter_is_gone():
    assert not (ROOT / "RELEASE_NOTES.md").exists()
    assert not list(ROOT.glob("RELEASE_NOTES_Elpis*.md"))
    archive = ROOT / "RELEASE_NOTES"
    assert (archive / "Elpis2.1.22.md").is_file()
    assert (archive / "Elpis2.1.23.md").is_file()
    assert (archive / "Elpis2.1.24.md").is_file()
    assert (archive / "README.md").is_file()

def test_readme_surfaces_release_notes_after_opening_abstract_before_install():
    text = (ROOT / "README.md").read_text()
    assert "## Abstract" not in text
    assert text.index("## Release Notes") < text.index("## Install and quick start")
    assert "RELEASE_NOTES/Elpis2.1.24.md" in text

def test_ecs_root_surface_is_consolidated():
    assert not (ROOT / "ECS_AUTHORITY").exists()
    assert not (ROOT / "ECS_AUTHORITY_HEADER.md").exists()
    assert (ROOT / "ECS/ECS_AUTHORITY/STRUCTURAL_R0").is_dir()
    assert (ROOT / "ECS/ECS_AUTHORITY_HEADER.md").is_file()
    assert (ROOT / "ECS/science").is_dir()

def test_branch40_closed_claim_material_is_present():
    p = ROOT / "ECS/science/BRANCH40_WEAK_S3_DYNAMICAL_RELEVANCE/SCIENTIFIC_CLOSURE.json"
    text = p.read_text()
    assert "PASS_BRANCH40_WEAK_S3_DYNAMICAL_RELEVANCE" in text
    assert "Outcome_A_RETAIN_FULL_ACTIVE_S3" in text

def test_current_release_note_declares_version_once():
    version = (ROOT / "VERSION").read_text().strip()
    note = (ROOT / f"RELEASE_NOTES/Elpis{version}.md").read_text()
    assert re.findall(r"(?m)^## Version: v([0-9]+\.[0-9]+\.[0-9]+)\s*$", note) == [version]
