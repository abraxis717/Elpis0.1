"""Negative branches must veto for their intended diagnostic.

Audits are isolated from pipeline execution here; release qualification also
executes genuine installed R0/R1 transactions. Old-code bypass evidence is
required before accepting a new guard mutation.
"""
import ast
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]


class Veto(Exception):
    pass


def isolated(version, function, tmp_path):
    path = REPO / f"runtime/{version}/src/elpis_runtime_{version.lower()}/transaction.py"
    tree = ast.parse(path.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function)
    ns = {"os": os, "json": json, "CANONICAL_ROOT": str(tmp_path / "canonical"),
          "FORBIDDEN_PREFIXES": (), "AUDITED_MODULES": ("first", "second"),
          "R0_ROOT": str(tmp_path / "R0"), "_digest": lambda data: data,
          "R0ImportEscapeError": Veto, "R1DependencyEscapeError": Veto,
          "R1CanonicalMutationError": Veto}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), ns)
    return ns


@pytest.mark.parametrize("version", ["R0", "R1"])
@pytest.mark.parametrize("case,marker", [
    ("outside", "OUTSIDE_CANONICAL"),
    ("prefix_collision", "OUTSIDE_CANONICAL"),
    ("unresolved", "UNRESOLVED_IMPORT"),
    ("no_file", "NO_MODULE_FILE"),
    ("legacy", "FORBIDDEN_ROOT"),
    ("extension", "FORBIDDEN_ROOT"),
])
def test_dependency_mutations(version, case, marker, monkeypatch, tmp_path):
    ns = isolated(version, "_dependency_escape_audit", tmp_path)
    canonical = Path(ns["CANONICAL_ROOT"])
    module_file = canonical / "pkg/module.py"
    if case == "outside":
        module_file = tmp_path / "outside/module.py"
    if case == "prefix_collision":
        module_file = Path(str(canonical) + "-evil/module.py")
    if case == "legacy":
        ns["FORBIDDEN_PREFIXES"] = (str(canonical / "pkg"),)
    if case == "extension":
        monkeypatch.setenv("ELPIS_FORBIDDEN_ROOTS", os.pathsep.join((str(tmp_path / "other"), str(canonical / "pkg"))))
    def imported(name):
        if case == "unresolved":
            raise ImportError("planted missing dependency")
        if case == "no_file":
            return SimpleNamespace()
        return SimpleNamespace(__file__=str(module_file))
    monkeypatch.setattr("importlib.import_module", imported)
    with pytest.raises(Veto, match=marker):
        ns["_dependency_escape_audit"]()


@pytest.mark.parametrize("version", ["R0", "R1"])
def test_clean_actual_resolved_count(version, monkeypatch, tmp_path):
    ns = isolated(version, "_dependency_escape_audit", tmp_path)
    monkeypatch.setattr("importlib.import_module", lambda name: SimpleNamespace(
        __file__=str(Path(ns["CANONICAL_ROOT"]) / name / "module.py")))
    result = ns["_dependency_escape_audit"]()
    assert result["modules_checked"] == len(result["resolved_modules"]) == 2
    assert result["status"] == "CLEAN"


@pytest.mark.parametrize("report,marker", [
    (None, "R0_AUDIT_REPORT_MISSING"),
    ({"disposition": "wrong"}, "R0_NOT_QUALIFIED"),
    ({}, "CANONICAL_FIELD_ABSENT"),
    ({"canonical_assembly_modified": True}, "CANONICAL_MODIFIED"),
    ({"canonical_assembly_modified": 0}, "CANONICAL_MODIFIED"),
])
def test_nonmutation_evidence(report, marker, tmp_path):
    ns = isolated("R1", "_canonical_nonmutation_check", tmp_path)
    if report is not None:
        report.setdefault("disposition", "ELPIS_RUNTIME_INTEGRATION_R0_DETERMINISTIC_TRANSACTION_QUALIFIED")
        target = tmp_path / "R0_Audit/FINAL_REPORT.json"
        target.parent.mkdir()
        target.write_text(json.dumps(report))
    with pytest.raises(Veto, match=marker):
        ns["_canonical_nonmutation_check"]()


def test_dependency_audits_have_mechanical_parity():
    nodes = []
    for version in ("R0", "R1"):
        path = REPO / f"runtime/{version}/src/elpis_runtime_{version.lower()}/transaction.py"
        tree = ast.parse(path.read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_dependency_escape_audit")
        for branch in ast.walk(node):
            if isinstance(branch, ast.Raise):
                branch.exc = ast.Name(id="PACKAGE_SPECIFIC_VETO", ctx=ast.Load())
        nodes.append(ast.dump(node, include_attributes=False))
    assert nodes[0] == nodes[1]


def test_r1_build_directory_is_resolved_lazily(tmp_path):
    ns = isolated("R1", "_ensure_dirs", tmp_path)
    target = tmp_path / "transaction-output"
    ns["BUILD_DIR"] = ""
    ns["_resolve_build_dir"] = lambda: str(target)
    ns["_ensure_dirs"]()
    assert target.is_dir()
    assert ns["BUILD_DIR"] == str(target)
