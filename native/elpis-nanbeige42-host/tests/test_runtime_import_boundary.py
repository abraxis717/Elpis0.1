from pathlib import Path


def test_runtime_package_does_not_import_phase_scripts():
    root = Path(__file__).parents[1] / "src" / "elpis_nanbeige42_host"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    assert "experiments.markov_header" not in text
    assert "p13_phase4" not in text
