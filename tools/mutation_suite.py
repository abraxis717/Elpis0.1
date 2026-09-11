#!/usr/bin/env python3
"""Mutation suite for tools/verify_public_release.py.

RATIONALE
  A verifier with no mutation suite is a self-report about itself. Every
  guard below was, at some point, either unreachable or unbound; three of
  them (M2, M6, M7) were demonstrated to pass a deliberately planted payload
  before the ephemeral-path fix. This file exists so that a guard cannot be
  weakened without a red test.

CONTRACT
  Each case copies the repository to a THROWAWAY directory, seals a
  PROVISIONAL manifest there, applies the mutation, runs the verifier against
  that copy, and asserts the observed exit code and diagnostic. Nothing here
  touches the working tree, and no published manifest is ever rewritten: the
  seal happens only inside the temporary copy.

  The provisional seal means this suite proves that guards FIRE. It does not
  verify the release -- that is the separate clean-clone run of
  verify_public_release.py against the real sealed manifest.

  expect = 1  the verifier MUST reject this mutation
  expect = 0  control: the verifier MUST NOT reject a clean tree

  Each negative case additionally asserts an expected DIAGNOSTIC MARKER in the
  verifier's output. An exit code alone is not sufficient evidence that the
  guard under test fired: any unrelated failing check produces exit 1 and
  would make a broken target guard look green.

CLAIMS NOT MADE
  Passing this suite does not mean the release is correct. It means the
  enumerated negative branches are reachable and bound.

CLI
  python tools/mutation_suite.py            # run all cases
  python tools/mutation_suite.py -v         # print verifier output per case
No network. Deterministic apart from the temporary directory path.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VERIFIER_REL = "tools/verify_public_release.py"
SEALER_REL = "tools/seal_release.py"

FAKE_AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
FAKE_PRIVATE_PATH_ROOT = "/mnt/" + "primesauce"
FAKE_PRIVATE_PATH = FAKE_PRIVATE_PATH_ROOT + "/Elpis_Canon"

IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
    ".ruff_cache", ".venv", "build", "dist", "*.egg-info",
)


# ---------------------------------------------------------------------------
# mutations
# ---------------------------------------------------------------------------

def _manifest_rel(root: Path) -> str:
    proc = subprocess.run(
        [sys.executable, str(root / VERIFIER_REL), "--print-manifest"],
        capture_output=True, text=True, cwd=root,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise AssertionError(f"manifest selection failed: {proc.stderr}")
    return proc.stdout.strip()


def _seal_provisional(root: Path) -> None:
    """Seal the copy's manifest. --i-am-rewriting-history is correct here and
    only here: the target is a temporary directory, never the repository."""
    proc = subprocess.run(
        [sys.executable, str(root / SEALER_REL), "--provisional",
         "--i-am-rewriting-history"],
        capture_output=True, text=True, cwd=root,
    )
    if proc.returncode != 0:
        raise AssertionError(f"provisional seal failed: {proc.stderr.strip()}")


def _reseal(root: Path, rel: str) -> None:
    """Regenerate one manifest digest, as an ordinary commit would.

    Without this, every content mutation is caught by the digest check and
    the mutation never reaches the guard under test.
    """
    import hashlib

    manifest = root / _manifest_rel(root)
    data = json.loads(manifest.read_text())
    target = root / rel
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    for entry in data["files"]:
        if entry["path"] == rel:
            entry["sha256"] = digest
            break
    else:
        raise AssertionError(f"{rel} not declared in manifest")
    manifest.write_text(json.dumps(data, indent=2) + "\n")


def _rebind_allowlist_containing_file(root: Path, rel: str) -> None:
    # Acknowledge one deliberate fixture-file edit in a throwaway case.
    import hashlib

    allowlist_rel = "tools/public_scan_allowlist.json"
    allowlist_path = root / allowlist_rel
    entries = json.loads(allowlist_path.read_text())
    digest = hashlib.sha256((root / rel).read_bytes()).hexdigest()

    changed = 0
    for entry in entries:
        if entry.get("path") == rel:
            if "file_sha256" not in entry:
                raise AssertionError(f"{rel}: allowlist entry missing file_sha256")
            entry["file_sha256"] = digest
            changed += 1

    if changed == 0:
        raise AssertionError(f"{rel}: no allowlist entries for containing-file rebind")

    allowlist_path.write_text(json.dumps(entries, indent=2) + "\n")
    _reseal(root, allowlist_rel)


def m0_clean(root: Path) -> None:
    """Control: an unmutated tree must verify."""


def m1_secret_in_declared_scan_skipped_file(root: Path) -> None:
    """B2: a secret inside a file formerly exempted by bare FILENAME.

    Resealing the manifest reproduces the realistic commit flow, so the
    digest check cannot mask the scanner's blind spot.
    """
    rel = "components/DarwinianMatrix/ecology/transaction.py"
    target = root / rel
    target.write_text(target.read_text() + f'\nAWS_KEY = "{FAKE_AWS_KEY}"\n')
    _reseal(root, rel)


def m1b_private_path_in_scan_skipped_file(root: Path) -> None:
    """B2: an operator-private absolute path in a name-exempted file."""
    rel = "native/elpis-header/src/elpis_header/core/transaction.py"
    target = root / rel
    target.write_text(target.read_text() + f'\n# {FAKE_PRIVATE_PATH}\n')
    _reseal(root, rel)


def m2_source_under_build_dir(root: Path) -> None:
    """B1: executable source hidden under any path component named build."""
    d = root / "components" / "build"
    d.mkdir(parents=True, exist_ok=True)
    (d / "payload.py").write_text("import os\nos.system('echo pwned')\n")


def m6_binary_under_build_dir(root: Path) -> None:
    """B1: an unreviewed shared object under an ephemeral path."""
    d = root / "runtime" / "build"
    d.mkdir(parents=True, exist_ok=True)
    (d / "libpayload.so").write_bytes(bytes(range(256)) * 8)


def m7_payload_under_pycache(root: Path) -> None:
    """B1: a non-.pyc file smuggled into a __pycache__ directory."""
    d = root / "src" / "__pycache__"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.py").write_text(f'AWS = "{FAKE_AWS_KEY}"\n')


def m1c_new_secret_beside_allowlisted_findings(root: Path) -> None:
    """B2: a file that legitimately carries allowlisted fixtures must still
    fire on a NEW literal. This is the case a whole-file exemption -- by name
    or by exact path -- cannot catch."""
    rel = "tests/test_ci_secret_scan.py"
    target = root / rel
    target.write_text(target.read_text() + f'\nNEW_KEY = "{FAKE_AWS_KEY}"\n')
    _reseal(root, rel)
    _rebind_allowlist_containing_file(root, rel)


def m1d_extra_occurrence_of_allowlisted_literal(root: Path) -> None:
    """B2: allowlist entries bind an occurrence COUNT. Duplicating an already
    allowlisted literal changes the count and must fire."""
    rel = "tools/ci_secret_scan.py"
    target = root / rel
    target.write_text(target.read_text() + f"\n# {FAKE_PRIVATE_PATH_ROOT}\n")
    _reseal(root, rel)
    _rebind_allowlist_containing_file(root, rel)


def m1e_stale_allowlist_entry(root: Path) -> None:
    """B2: removing an allowlisted literal must fire too. A permanently
    over-broad allowlist is a silent re-opening of the hole."""
    rel = "tools/ci_secret_scan.py"
    target = root / rel
    text = target.read_text()
    target.write_text(text.replace(FAKE_PRIVATE_PATH_ROOT, "/redacted", 1))
    _reseal(root, rel)
    _rebind_allowlist_containing_file(root, rel)


def m2b_pyc_under_build_dir(root: Path) -> None:
    """B1: compiled bytecode is executable. The earlier fix allowed .pyc
    inside ephemeral paths, which exempted it from the artifact rejection."""
    d = root / "components" / "build"
    d.mkdir(parents=True, exist_ok=True)
    (d / "payload.pyc").write_bytes(bytes(range(256)) * 2)


def m10_benign_source_under_tool_cache(root: Path) -> None:
    """B1: a tool cache in a release checkout is a failure regardless of
    content. No secret pattern is planted -- the file is benign Python."""
    d = root / ".pytest_cache" / "v"
    d.mkdir(parents=True, exist_ok=True)
    (d / "helper.py").write_text("def helper():\n    return 1\n")


def m3_tamper_declared_file(root: Path) -> None:
    """Control for the digest binding: declared content must not drift."""
    readme = root / "README.md"
    readme.write_text(readme.read_text() + "\n<!-- tamper -->\n")


def m4_undeclared_file_normal_path(root: Path) -> None:
    """Control for manifest completeness at an ordinary path."""
    (root / "components" / "stray_module.py").write_text("x = 1\n")


def m8_runtime_admission_flag_flipped(root: Path) -> None:
    """The AST boundary check must reject a flipped admission default."""
    rel = "src/elpis_reference/structural_guidance/admission.py"
    target = root / rel
    text = target.read_text()
    mutated = text.replace("enabled: bool = False", "enabled: bool = True", 1)
    if mutated == text:
        raise AssertionError(f"admission default not found in {rel}")
    target.write_text(mutated)
    _reseal(root, rel)


def m9_manifest_count_drift(root: Path) -> None:
    """A claimed file_count must be recomputed, never trusted."""
    manifest = root / _manifest_rel(root)
    data = json.loads(manifest.read_text())
    data["file_count"] = int(data["file_count"]) + 1
    manifest.write_text(json.dumps(data, indent=2) + "\n")


def m11_invalid_utf8_in_declared_text(root: Path) -> None:
    """The scanner must fail closed on declared text it cannot decode.

    errors="replace" was as unsafe as a bare except: it never raised, so a
    UTF-16 encoded secret decoded to interleaved NULs, matched no pattern, and
    the file passed. Verified: this exact mutation passed before the fix.
    """
    rel = "docs/BUILD.md"
    target = root / rel
    target.write_bytes(
        target.read_bytes()
        + f'\nAWS_KEY = "{FAKE_AWS_KEY}"\n'.encode("utf-16")
    )
    _reseal(root, rel)


def m11b_raw_invalid_byte_in_declared_text(root: Path) -> None:
    """An ASCII secret after an invalid byte. Already caught before the fix;
    retained so the decode hardening cannot regress it."""
    rel = "docs/BUILD.md"
    target = root / rel
    target.write_bytes(
        target.read_bytes() + b"\xff\n" + f'KEY = "{FAKE_AWS_KEY}"\n'.encode()
    )
    _reseal(root, rel)


def m12_new_finding_kind(root: Path) -> None:
    rel = "tests/test_ci_secret_scan.py"
    target = root / rel
    target.write_text(target.read_text() + "\n# BEGIN " + "PRIVATE KEY\n")
    _reseal(root, rel)
    _rebind_allowlist_containing_file(root, rel)


def m13_empty_cache(root: Path) -> None:
    (root / ".mypy_cache").mkdir()


def m14_symlink_escape(root: Path) -> None:
    (root / "escape-link").symlink_to(root.parent / "outside")


def m15_readme_declared_release_drift(root: Path) -> None:
    """Declared README release identity must agree with VERSION.

    Resealing deliberately removes manifest digest drift as a confounder.
    The verifier must reject the semantically inconsistent declaration.
    """
    rel = "README.md"
    target = root / rel
    version = (root / "VERSION").read_text().strip()

    stale = (
        "0.0.0"
        if version != "0.0.0"
        else "9.9.9"
    )

    pattern = (
        rf"(?m)^\*\*Release line: "
        rf"Elpis{re.escape(version)}\*\*$"
    )

    mutated, count = re.subn(
        pattern,
        f"**Release line: Elpis{stale}**",
        target.read_text(),
        count=1,
    )

    if count != 1:
        raise AssertionError(
            "canonical README release declaration "
            f"not found for VERSION={version}"
        )

    target.write_text(mutated)
    _reseal(root, rel)


def m16_release_notes_declared_version_drift(
    root: Path,
) -> None:
    """Canonical current release-note version must agree with VERSION.

    Match the declaration grammar itself rather than merely searching for
    the current version as an arbitrary substring elsewhere in the file.
    """
    version = (root / "VERSION").read_text().strip()
    rel = f"RELEASE_NOTES/Elpis{version}.md"
    target = root / rel

    stale = "0.0.0"

    pattern = (
        r"(?m)^## Version: v"
        r"[0-9]+\.[0-9]+\.[0-9]+\s*$"
    )

    mutated, count = re.subn(
        pattern,
        f"## Version: v{stale}",
        target.read_text(),
        count=1,
    )

    if count != 1:
        raise AssertionError(
            "canonical current release-note "
            "version declaration not found"
        )

    target.write_text(mutated)
    _reseal(root, rel)


CASES: tuple[tuple[str, object, int, str], ...] = (
    (
        "M15 README declared release drift",
        m15_readme_declared_release_drift,
        1,
        "DECLARED_TEXT_VERSION_MISMATCH: README.md",
    ),
    (
        "M16 RELEASE_NOTES declared version drift",
        m16_release_notes_declared_version_drift,
        1,
        "DECLARED_TEXT_VERSION_MISMATCH: RELEASE_NOTES/Elpis",
    ),
    ("M12 new finding kind in allowlisted fixture",
     m12_new_finding_kind, 1, "SECRET:private key"),
    ("M13 empty cache directory",
     m13_empty_cache, 1, "EPHEMERAL ARTIFACT PRESENT"),
    ("M14 symlink escape",
     m14_symlink_escape, 1, "SYMLINK ESCAPE"),
    ("M0  clean tree (control)",
     m0_clean, 0, ""),
    ("M1  secret in formerly name-exempt file",
     m1_secret_in_declared_scan_skipped_file, 1, "SECRET:AWS key"),
    ("M1b private path in formerly name-exempt file",
     m1b_private_path_in_scan_skipped_file, 1, "PRIVATE_PATH"),
    ("M1c new secret beside allowlisted fixtures",
     m1c_new_secret_beside_allowlisted_findings, 1, "not allowlisted"),
    ("M1d extra occurrence of allowlisted literal",
     m1d_extra_occurrence_of_allowlisted_literal, 1, "not allowlisted"),
    ("M1e allowlisted literal removed (stale entry)",
     m1e_stale_allowlist_entry, 1, "STALE ALLOWLIST ENTRY"),
    ("M2  source under build/",
     m2_source_under_build_dir, 1, "EPHEMERAL ARTIFACT PRESENT"),
    ("M2b .pyc under build/",
     m2b_pyc_under_build_dir, 1, "EPHEMERAL ARTIFACT PRESENT"),
    ("M3  tampered declared file (control)",
     m3_tamper_declared_file, 1, "DIGEST MISMATCH"),
    ("M4  undeclared file, normal path (control)",
     m4_undeclared_file_normal_path, 1, "UNDECLARED"),
    ("M6  binary .so under build/",
     m6_binary_under_build_dir, 1, "EPHEMERAL ARTIFACT PRESENT"),
    ("M7  payload under __pycache__/",
     m7_payload_under_pycache, 1, "EPHEMERAL ARTIFACT PRESENT"),
    ("M10 benign source under .pytest_cache/",
     m10_benign_source_under_tool_cache, 1, "EPHEMERAL ARTIFACT PRESENT"),
    ("M8  runtime admission default flipped",
     m8_runtime_admission_flag_flipped, 1, "guidance request gate default"),
    ("M11 utf-16 secret in declared text",
     m11_invalid_utf8_in_declared_text, 1, "TEXT_SCAN_DECODE_FAILED"),
    ("M11b invalid byte + ascii secret",
     m11b_raw_invalid_byte_in_declared_text, 1, "TEXT_SCAN_DECODE_FAILED"),
    ("M9  manifest file_count drift",
     m9_manifest_count_drift, 1, "file_count mismatch"),
)


# ---------------------------------------------------------------------------
# harness
# ---------------------------------------------------------------------------

def run_case(name: str, mutate, expect: int, marker: str, verbose: bool) -> dict:
    with tempfile.TemporaryDirectory(prefix="elpis_mut_") as td:
        root = Path(td) / "repo"
        shutil.copytree(REPO, root, ignore=IGNORE, symlinks=True)
        try:
            _seal_provisional(root)
            mutate(root)
        except AssertionError as exc:
            return {"name": name, "ok": False, "reason": f"SETUP_FAILED: {exc}",
                    "expected_exit": expect, "observed_exit": None, "marker_seen": False}

        proc = subprocess.run(
            [sys.executable, str(root / VERIFIER_REL)],
            capture_output=True, text=True, cwd=root,
        )
        observed = proc.returncode
        marker_seen = (not marker) or (marker in (proc.stdout + proc.stderr))
        ok = observed == expect and marker_seen
        if verbose or not ok:
            sys.stderr.write(f"--- {name} (expect {expect}, got {observed}) ---\n")
            sys.stderr.write(proc.stdout[-2000:] + "\n")
        if ok:
            reason = ""
        elif observed != expect and expect == 1:
            reason = "GUARD_DID_NOT_FIRE"
        elif observed != expect:
            reason = "FALSE_POSITIVE_ON_CLEAN_TREE"
        else:
            reason = f"WRONG_GUARD_FIRED (missing marker {marker!r})"

        return {
            "name": name,
            "ok": ok,
            "expected_exit": expect,
            "observed_exit": observed,
            "marker": marker,
            "marker_seen": marker_seen,
            "reason": reason,
        }


def main(argv: list[str]) -> int:
    verbose = "-v" in argv
    results = [run_case(n, f, e, m, verbose) for n, f, e, m in CASES]

    width = max(len(r["name"]) for r in results)
    for r in results:
        mark = "PASS" if r["ok"] else "FAIL"
        detail = "" if r["ok"] else f"  <- {r['reason']}"
        print(
            f"[{mark}] {r['name']:<{width}}  "
            f"expect={r['expected_exit']} got={r['observed_exit']} "
            f"marker={'yes' if r['marker_seen'] else 'NO':<3}{detail}"
        )

    failed = [r for r in results if not r["ok"]]
    print(
        f"\n{len(results) - len(failed)}/{len(results)} mutations correctly handled"
    )
    if failed:
        print("MUTATION SUITE FAILED: a release guard is unreachable or unbound")
        return 1
    print("MUTATION SUITE PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
