#!/usr/bin/env python3
"""Fail-closed, VERSION-driven public release verifier."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent

RELEASE_VERSION = (REPO / "VERSION").read_text(encoding="utf-8").strip()
# Ratified repository identities, never inferred from a manifest's claims.
RELEASE_IDENTITIES = {
    "2.1.2": {
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.3": {
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.4": {
        # Release-integrity successor only: no primitive/runtime closure moved.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # This field is the original Elpis2.0.0 distribution baseline, not predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.5": {
        # Furyan scientific-source successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.6": {
        # Security/integrity successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.7": {
        # README-paper successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.8": {
        # Runtime/correctness successor; the ratified Elpis2.0.0 primitive
        # closure identity remains the primitive baseline.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.9": {
        # Structural-correctness/runtime-boundary successor; primitive closure
        # remains the ratified Elpis2.0.0 baseline.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.10": {
        # Local release successor; primitive closure remains the ratified baseline.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.11": {
        # APW R0 evidence successor; primitive/runtime closure is unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.12": {
        # ECS structural-authority publication successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
    "2.1.13": {
        # Executable ECS R0 and repository-hardening successor; primitive/runtime closure unchanged.
        "primitive_closure_commit": "482d4064321392108b87124cd47343d9c748f5bc",
        # Original Elpis2.0.0 distribution baseline, not immediate predecessor.
        "base_release_commit": "c911af22e01ee35c441d65e8dbcad18694bdcb2a",
    },
}
RELEASE_MANIFEST_REL = Path(f"manifests/Elpis{RELEASE_VERSION}.RELEASE_MANIFEST.json")
DISTRIBUTION_MANIFEST_REL = Path(f"manifests/Elpis{RELEASE_VERSION}.DISTRIBUTION_MANIFEST.json")
MANIFEST_REL = (DISTRIBUTION_MANIFEST_REL
                if (REPO / DISTRIBUTION_MANIFEST_REL).exists()
                else RELEASE_MANIFEST_REL)
MANIFEST = REPO / MANIFEST_REL
IGNORE_PARTS = {".git"}
EPHEMERAL_PARTS = {"build", "dist", "__pycache__", ".venv",
                   ".pytest_cache", ".mypy_cache", ".ruff_cache"}
ALLOWLIST_REL = Path("tools/public_scan_allowlist.json")


def release_identity():
    identity = RELEASE_IDENTITIES.get(RELEASE_VERSION)
    if identity is None:
        raise ValueError(f"UNKNOWN_RELEASE_IDENTITY: {RELEASE_VERSION}")
    if any(value == "UNSEALED" for value in identity.values()):
        raise ValueError(f"UNSEALED_RELEASE_IDENTITY: {RELEASE_VERSION}")
    return identity


def ephemeral(rel: Path) -> bool:
    return bool(set(rel.parts) & EPHEMERAL_PARTS) or any(
        part.endswith(".egg-info") for part in rel.parts
    )


BINARY_SUFFIXES = {
    ".so", ".a", ".o", ".pyc",
    ".egg", ".gguf", ".safetensors", ".pt",
}

TEXT_SUFFIXES = {
    ".py", ".c", ".cpp", ".h",
    ".json", ".toml", ".yaml", ".yml",
    ".md", ".txt", ".cff", ".cmake", ".sh",
}

SECRET_PATTERNS = (
    (r"BEGIN " + "PRIVATE KEY", "private key"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub PAT"),
    (r"github_pat_[A-Za-z0-9_]{20,}", "GitHub PAT"),
    (r"sk-[A-Za-z0-9]{48,}", "OpenAI-style key"),
    (r"AKIA[A-Z0-9]{16}", "AWS key"),
    (r"AIza[A-Za-z0-9_-]{35}", "Google API key"),
)


def digest(path: Path) -> str:
    if path.is_symlink():
        payload = path.readlink().as_posix().encode()
    else:
        payload = path.read_bytes()

    return hashlib.sha256(payload).hexdigest()


def ignored(rel: Path) -> bool:
    return bool(set(rel.parts) & IGNORE_PARTS)


def release_paths() -> list[Path]:
    return sorted(path for path in REPO.rglob("*")
                  if not ignored(path.relative_to(REPO)))


def actual_files() -> set[str]:
    out: set[str] = set()

    for path in release_paths():
        rel = path.relative_to(REPO)

        if ignored(rel):
            continue

        if rel == MANIFEST_REL:
            continue

        if path.is_file() or path.is_symlink():
            out.add(rel.as_posix())

    return out


def load_manifest():
    errors = []

    if not MANIFEST.exists():
        return {}, [
            f"missing {MANIFEST_REL.as_posix()}"
        ]

    try:
        data = json.loads(MANIFEST.read_text())
    except Exception as exc:
        return {}, [f"invalid manifest: {exc}"]

    expected_schema = (
        "elpis.distribution-manifest.v1"
        if MANIFEST_REL == DISTRIBUTION_MANIFEST_REL
        else "elpis.release-manifest.v2"
    )

    try:
        identity = release_identity()
    except ValueError as exc:
        return data, [str(exc)]

    expected = {
        "schema": expected_schema,
        "release_name": f"Elpis{RELEASE_VERSION}",
        "release_tag": f"Elpis{RELEASE_VERSION}",
        "version": RELEASE_VERSION,
        "package_name": "elpis",
        "primitive_closure_commit": identity["primitive_closure_commit"],
        "runtime_status": "VALIDATED_SOURCE",
        "full_elpis_runtime_admission": True,
        "request_guidance_gate_default": False,
        "output_authority_granted": 0,
        "validation_authority_propagated": False,
        "generated_source_executed": False,
        "execution_authorized": False,
        "experiments_shipped": False,
        "nanbeige_host_shipped": False,
    }

    if RELEASE_VERSION != "2.1.2" or MANIFEST_REL == DISTRIBUTION_MANIFEST_REL:
        expected["base_release_commit"] = identity["base_release_commit"]
    if MANIFEST_REL == DISTRIBUTION_MANIFEST_REL:
        expected["distribution_version"] = RELEASE_VERSION
        expected["tag_immutable"] = True

    for key, value in expected.items():
        if data.get(key) != value:
            errors.append(
                f"manifest {key} mismatch: "
                f"{data.get(key)!r}"
            )

    return data, errors


def check_manifest():
    data, errors = load_manifest()
    entries = data.get("files", [])

    if not isinstance(entries, list):
        return False, errors + [
            "manifest files must be a list"
        ]

    declared = {}

    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("invalid manifest file entry")
            continue

        rel = entry.get("path")
        expected = entry.get("sha256")

        if not isinstance(rel, str) or not rel:
            errors.append("invalid manifest path")
            continue

        if rel in declared:
            errors.append(f"duplicate path: {rel}")
            continue

        if (
            not isinstance(expected, str)
            or len(expected) != 64
        ):
            errors.append(
                f"invalid digest for {rel}"
            )
            continue

        declared[rel] = expected

    actual = actual_files()

    for rel in sorted(set(declared) - actual):
        errors.append(f"MISSING: {rel}")

    for rel in sorted(actual - set(declared)):
        errors.append(f"UNDECLARED: {rel}")

    for rel in sorted(set(declared) & actual):
        if digest(REPO / rel) != declared[rel]:
            errors.append(
                f"DIGEST MISMATCH: {rel}"
            )

    if data.get("file_count") != len(declared):
        errors.append("manifest file_count mismatch")

    return not errors, errors


_DECLARED_TEXT_VERSION_PATTERNS = {
    "README.md": re.compile(
        r"(?m)^\*\*Release line: Elpis"
        r"([0-9]+\.[0-9]+\.[0-9]+)"
        r"\*\*[ \t]*$"
    ),
    "RELEASE_NOTES.md": re.compile(
        r"(?m)^## Version: v"
        r"([0-9]+\.[0-9]+\.[0-9]+)"
        r"[ \t]*$"
    ),
}


def check_declared_text_version():
    errors = []

    for rel, pattern in (
        _DECLARED_TEXT_VERSION_PATTERNS.items()
    ):
        path = REPO / rel

        try:
            text = path.read_text(
                encoding="utf-8",
                errors="strict",
            )
        except (OSError, UnicodeError) as exc:
            errors.append(
                "DECLARED_TEXT_VERSION_INVALID: "
                f"{rel}: {exc}"
            )
            continue

        matches = pattern.findall(text)

        if len(matches) != 1:
            errors.append(
                "DECLARED_TEXT_VERSION_INVALID: "
                f"{rel}: declarations={len(matches)}"
            )
            continue

        declared = matches[0]

        if declared != RELEASE_VERSION:
            errors.append(
                "DECLARED_TEXT_VERSION_MISMATCH: "
                f"{rel}: "
                f"declared={declared} "
                f"expected={RELEASE_VERSION}"
            )

    return not errors, errors


def check_package():
    errors = []
    data = tomllib.loads(
        (REPO / "pyproject.toml").read_text()
    )
    project = data["project"]

    if project.get("name") != "elpis":
        errors.append("package name is not elpis")

    if project.get("version") != RELEASE_VERSION:
        errors.append(f"package version is not {RELEASE_VERSION}")

    if (REPO / "VERSION").read_text().strip() != RELEASE_VERSION:
        errors.append("VERSION mismatch")

    if not any(
        isinstance(dep, str) and dep.startswith("scipy")
        for dep in project.get("dependencies", [])
    ):
        errors.append("SciPy dependency missing")

    return not errors, errors


def constant_assignment(path: Path, name: str):
    tree = ast.parse(
        path.read_text(),
        filename=str(path),
    )

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == name
                    and isinstance(node.value, ast.Constant)
                ):
                    return node.value.value

        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and isinstance(node.value, ast.Constant)
        ):
            return node.value.value

    raise RuntimeError(
        f"{name} constant assignment not found"
    )


def check_runtime_boundary():
    errors = []

    root = (
        REPO
        / "src/elpis_reference/structural_guidance"
    )

    try:
        admitted = constant_assignment(
            root / "authority.py",
            "FULL_ELPIS_RUNTIME_ADMISSION",
        )
    except Exception as exc:
        errors.append(str(exc))
    else:
        if admitted is not True:
            errors.append(
                "FULL_ELPIS_RUNTIME_ADMISSION != True"
            )

    admission_tree = ast.parse(
        (root / "admission.py").read_text()
    )

    default = None

    for node in admission_tree.body:
        if not (
            isinstance(node, ast.ClassDef)
            and node.name
            == "StructuralGuidanceAdmissionConfig"
        ):
            continue

        for item in node.body:
            if (
                isinstance(item, ast.AnnAssign)
                and isinstance(item.target, ast.Name)
                and item.target.id == "enabled"
                and isinstance(item.value, ast.Constant)
            ):
                default = item.value.value

    if default is not False:
        errors.append(
            "guidance request gate default != False"
        )

    runtime = root / "runtime.py"
    tree = ast.parse(
        runtime.read_text(),
        filename=str(runtime),
    )

    execution_false = False
    validation_false = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id
                in {"compile", "eval", "exec"}
            ):
                errors.append(
                    f"execution call {node.func.id}"
                )

            for kw in node.keywords:
                if (
                    kw.arg == "execution_authorized"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is False
                ):
                    execution_false = True

                if (
                    kw.arg == "validation_authorized"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is False
                ):
                    validation_false = True

        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in {
                    "subprocess",
                    "importlib",
                }:
                    errors.append(
                        f"execution import {alias.name}"
                    )

        if isinstance(node, ast.ImportFrom):
            if node.module in {
                "subprocess",
                "importlib",
            }:
                errors.append(
                    f"execution import {node.module}"
                )

    # `_terminal_result()` builds the terminal fields in a literal
    # dictionary and then splats that dictionary into the dataclass.
    # Recognize that real construction shape rather than requiring
    # direct constructor keyword arguments.
    terminal_fn = next(
        (
            node
            for node in tree.body
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "_terminal_result"
            )
        ),
        None,
    )

    if terminal_fn is None:
        errors.append(
            "_terminal_result function absent"
        )
    else:
        for node in ast.walk(terminal_fn):
            if not isinstance(node, ast.Dict):
                continue

            for key, value in zip(
                node.keys,
                node.values,
            ):
                if not (
                    isinstance(key, ast.Constant)
                    and isinstance(key.value, str)
                    and isinstance(value, ast.Constant)
                    and value.value is False
                ):
                    continue

                if key.value == "execution_authorized":
                    execution_false = True

                if key.value == "validation_authorized":
                    validation_false = True

    # Independently require the terminal dataclass validator to
    # fail closed if either bit is ever forged true.
    result_class = next(
        (
            node
            for node in tree.body
            if (
                isinstance(node, ast.ClassDef)
                and node.name
                == "StructuralGuidanceRuntimeResultV1"
            )
        ),
        None,
    )

    execution_guard = False
    validation_guard = False

    if result_class is None:
        errors.append(
            "StructuralGuidanceRuntimeResultV1 absent"
        )
    else:
        validate_fn = next(
            (
                node
                for node in result_class.body
                if (
                    isinstance(node, ast.FunctionDef)
                    and node.name == "validate"
                )
            ),
            None,
        )

        if validate_fn is None:
            errors.append(
                "terminal validate method absent"
            )
        else:
            for node in ast.walk(validate_fn):
                if not (
                    isinstance(node, ast.Compare)
                    and len(node.ops) == 1
                    and isinstance(node.ops[0], ast.IsNot)
                    and len(node.comparators) == 1
                    and isinstance(
                        node.comparators[0],
                        ast.Constant,
                    )
                    and node.comparators[0].value is False
                    and isinstance(node.left, ast.Attribute)
                    and isinstance(node.left.value, ast.Name)
                    and node.left.value.id == "self"
                ):
                    continue

                if node.left.attr == "execution_authorized":
                    execution_guard = True

                if node.left.attr == "validation_authorized":
                    validation_guard = True

    if not execution_false:
        errors.append(
            "terminal execution_authorized=False absent"
        )

    if not validation_false:
        errors.append(
            "terminal validation_authorized=False absent"
        )

    if not execution_guard:
        errors.append(
            "execution authority fail-closed guard absent"
        )

    if not validation_guard:
        errors.append(
            "validation authority fail-closed guard absent"
        )

    if "VALIDATED_SOURCE" not in runtime.read_text():
        errors.append(
            "VALIDATED_SOURCE terminal absent"
        )

    return not errors, errors


def check_public_boundary():
    errors = []

    if (REPO / "experiments").exists():
        errors.append(
            "top-level experiments/ shipped"
        )

    if (
        REPO / "native/elpis-nanbeige42-host"
    ).exists():
        errors.append(
            "Nanbeige host adapter shipped"
        )

    return not errors, errors


def scan_findings():
    from collections import Counter
    findings = Counter()
    errors = []
    for path in release_paths():
        if not (path.is_file() or path.is_symlink()):
            continue
        rel = path.relative_to(REPO).as_posix()
        if path.suffix not in TEXT_SUFFIXES and path.name not in {"VERSION", "LICENSE", "CMakeLists.txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeError) as exc:
            errors.append(f"TEXT_SCAN_DECODE_FAILED: {rel}: {exc}")
            continue
        patterns = list(SECRET_PATTERNS) + [
            (re.escape("/mnt/" + "primesauce"), "PRIVATE_PATH"),
            (re.escape("/home/" + "joe"), "PRIVATE_PATH"),
        ]
        for pattern, desc in patterns:
            kind = desc if desc == "PRIVATE_PATH" else f"SECRET:{desc}"
            for match in re.finditer(pattern, text):
                literal_digest = hashlib.sha256(match.group().encode("utf-8")).hexdigest()
                findings[(rel, kind, literal_digest)] += 1
    return findings, errors


def emitted_allowlist():
    findings, errors = scan_findings()
    if errors:
        raise ValueError("; ".join(errors))
    return [{
                "path": p, "kind": k, "sha256": h, "count": n,
                "file_sha256": digest(REPO / p),
            }
            for (p, k, h), n in sorted(findings.items())]


def check_private_data():
    findings, errors = scan_findings()
    try:
        entries = json.loads((REPO / ALLOWLIST_REL).read_text(encoding="utf-8"))
        allowlist = {}
        for entry in entries:
            key = (entry["path"], entry["kind"], entry["sha256"])
            if key in allowlist or type(entry["count"]) is not int or entry["count"] < 1:
                raise ValueError("invalid or duplicate allowlist entry")
            if type(entry.get("file_sha256")) is not str or not re.fullmatch(r"[0-9a-f]{64}", entry["file_sha256"]):
                raise ValueError("allowlist entry missing valid file_sha256")
            file_path = REPO / entry["path"]
            if not file_path.is_file() or digest(file_path) != entry["file_sha256"]:
                raise ValueError(f"allowlist containing-file digest mismatch: {entry['path']}")
            allowlist[key] = entry["count"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return False, errors + [f"INVALID ALLOWLIST: {exc}"]
    for key, count in sorted(findings.items()):
        if count > allowlist.get(key, 0):
            errors.append(f"{key[1]}: {key[0]}: not allowlisted (count {count})")
    for key, count in sorted(allowlist.items()):
        if findings.get(key, 0) < count:
            errors.append(f"STALE ALLOWLIST ENTRY: {key[0]}: {key[1]}")
    return not errors, errors


def check_artifacts():
    errors = []

    for path in release_paths():
        rel = path.relative_to(REPO)
        if ephemeral(rel):
            errors.append(f"EPHEMERAL ARTIFACT PRESENT: {rel}")
        if path.suffix in BINARY_SUFFIXES:
            errors.append(
                f"BINARY/ARTIFACT: {rel}"
            )

        if path.is_symlink():
            target = path.resolve()

            if not target.is_relative_to(REPO):
                errors.append(
                    f"SYMLINK ESCAPE: {rel}"
                )

    return not errors, errors


def main() -> int:
    if "--print-manifest" in sys.argv:
        print(MANIFEST_REL.as_posix())
        return 0
    if "--emit-allowlist" in sys.argv:
        print(json.dumps(emitted_allowlist(), indent=2) )
        return 0
    checks = (
        ("Elpis2 manifest", check_manifest),
        ("Package identity", check_package),
        ("Declared-text version", check_declared_text_version),
        ("Runtime boundary", check_runtime_boundary),
        ("Portable public boundary", check_public_boundary),
        ("Secret/private-path scan", check_private_data),
        ("Binary/artifact scan", check_artifacts),
    )

    passed = True

    for name, fn in checks:
        ok, errors = fn()
        print(
            f"[{'PASS' if ok else 'FAIL'}] {name}"
        )

        if not ok:
            passed = False

        for error in errors:
            print(f"  -> {error}")

    if passed:
        print(
            f"PASS: Elpis{RELEASE_VERSION} public release verified"
        )
        return 0

    print(
        f"FAIL: Elpis{RELEASE_VERSION} public release verification failed"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
