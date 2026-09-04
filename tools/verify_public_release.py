#!/usr/bin/env python3
"""Fail-closed public verifier for Elpis2.0.0."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent

RELEASE_MANIFEST_REL = Path(
    "manifests/Elpis2.0.0.RELEASE_MANIFEST.json"
)

DISTRIBUTION_MANIFEST_REL = Path(
    "manifests/Elpis2.0.0.DISTRIBUTION_MANIFEST.json"
)

MANIFEST_REL = (
    DISTRIBUTION_MANIFEST_REL
    if (REPO / DISTRIBUTION_MANIFEST_REL).exists()
    else RELEASE_MANIFEST_REL
)

MANIFEST = REPO / MANIFEST_REL

IGNORE_PARTS = {
    ".git",
    "build",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
}

BINARY_SUFFIXES = {
    ".so", ".a", ".o", ".pyc",
    ".egg", ".gguf", ".safetensors", ".pt",
}

TEXT_SUFFIXES = {
    ".py", ".c", ".cpp", ".h",
    ".json", ".toml", ".yaml", ".yml",
    ".md", ".txt", ".cff", ".cmake", ".sh",
}

SCAN_SKIP_NAMES = {
    "verify_public_release.py",
    "ci_secret_scan.py",
    "test_ci_secret_scan.py",
    "transaction.py",
    "test_r0_transaction.py",
}

SECRET_PATTERNS = (
    (r"BEGIN PRIVATE KEY", "private key"),
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


def actual_files() -> set[str]:
    out: set[str] = set()

    for path in REPO.rglob("*"):
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

    expected = {
        "schema": expected_schema,
        "release_name": "Elpis2.0.0",
        "release_tag": "Elpis2.0.0",
        "version": "2.0.0",
        "package_name": "elpis",
        "primitive_closure_commit":
            "482d4064321392108b87124cd47343d9c748f5bc",
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

    if MANIFEST_REL == DISTRIBUTION_MANIFEST_REL:
        expected["base_release_commit"] = (
            "c911af22e01ee35c441d65e8dbcad18694bdcb2a"
        )
        expected["distribution_version"] = "2.0.0"
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


def check_package():
    errors = []
    data = tomllib.loads(
        (REPO / "pyproject.toml").read_text()
    )
    project = data["project"]

    if project.get("name") != "elpis":
        errors.append("package name is not elpis")

    if project.get("version") != "2.0.0":
        errors.append("package version is not 2.0.0")

    if (REPO / "VERSION").read_text().strip() != "2.0.0":
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


def check_private_data():
    errors = []

    for rel in sorted(actual_files()):
        path = REPO / rel

        if (
            path.suffix not in TEXT_SUFFIXES
            or path.name in SCAN_SKIP_NAMES
            or path.is_symlink()
        ):
            continue

        try:
            text = path.read_text(errors="replace")
        except Exception:
            continue

        for pattern, desc in SECRET_PATTERNS:
            if re.search(pattern, text):
                errors.append(
                    f"SECRET {desc}: {rel}"
                )

        for private in (
            "/mnt/primesauce",
            "/home/joe",
        ):
            if private in text:
                errors.append(
                    f"PRIVATE PATH {private}: {rel}"
                )

    return not errors, errors


def check_artifacts():
    errors = []

    for rel in sorted(actual_files()):
        path = REPO / rel

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
    checks = (
        ("Elpis2 manifest", check_manifest),
        ("Package identity", check_package),
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
            "PASS: Elpis2.0.0 public release verified"
        )
        return 0

    print(
        "FAIL: Elpis2.0.0 public release verification failed"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
