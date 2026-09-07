"""Successor regressions for authority-hygiene closure."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_public_release_manifest_is_not_current_authority():
    assert not (
        ROOT / "manifests" / "PUBLIC_RELEASE_MANIFEST.json"
    ).exists()


def test_versioned_release_manifests_remain_present():
    manifests = ROOT / "manifests"

    for version in (
        "Elpis2.0.0.RELEASE_MANIFEST.json",
        "Elpis2.1.0.RELEASE_MANIFEST.json",
        "Elpis2.1.1.RELEASE_MANIFEST.json",
        "Elpis2.1.2.RELEASE_MANIFEST.json",
        "Elpis2.1.3.RELEASE_MANIFEST.json",
        "Elpis2.1.4.RELEASE_MANIFEST.json",
        "Elpis2.1.5.RELEASE_MANIFEST.json",
        "Elpis2.1.6.RELEASE_MANIFEST.json",
        "Elpis2.1.7.RELEASE_MANIFEST.json",
        "Elpis2.1.8.RELEASE_MANIFEST.json",
    ):
        assert (manifests / version).is_file()
