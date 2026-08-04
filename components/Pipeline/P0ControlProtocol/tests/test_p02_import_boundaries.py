"""P0.2 Gate 12 - Import and scope boundary tests.

Verify P0.2 modules do not import forbidden packages or use
forbidden operations (subprocess, network, filesystem, etc.).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

# P0.2 module source directory
P02_SRC = Path(__file__).parent.parent / "src" / "elpis_p0"

# Forbidden imports for P0.2
FORBIDDEN_IMPORTS = {
    "CNumPyCortex",
    "GeodesicWorldModel",
    "Chronos",
    "BlackCore",
    "HebbianBrain",
    "Lumen",
    "LoRAManifold",
    "requests",
    "http",
    "urllib",
    "sqlite3",
    "faiss",
    "socket",
}

# Forbidden operations (function names / module-level calls)
FORBIDDEN_OPERATIONS = {
    "os.system",
    "subprocess.run",
    "subprocess.Popen",
    "eval",
    "exec",
    "__import__",
    "compile",
}


def get_p02_modules() -> list[Path]:
    """Find all P0.2 source files (excluding pre-P0.2 files)."""
    p02_files = [
        "expansion_contracts.py",
        "expansion.py",
        "authority_bridge.py",
        "seeds.py",
        "fold.py",
        "p02_runner.py",
        "p02_cli.py",
    ]
    return [P02_SRC / f for f in p02_files if (P02_SRC / f).exists()]


class TestImportBoundaries:
    def test_no_forbidden_imports(self):
        """P0.2 modules must not import forbidden packages."""
        violations = []
        for module_path in get_p02_modules():
            tree = ast.parse(module_path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_level = alias.name.split(".")[0]
                        if top_level in FORBIDDEN_IMPORTS:
                            violations.append(
                                f"{module_path.name}: import {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top_level = node.module.split(".")[0]
                        if top_level in FORBIDDEN_IMPORTS:
                            violations.append(
                                f"{module_path.name}: from {node.module} import ..."
                            )
        assert not violations, f"Forbidden imports found: {violations}"

    def test_no_forbidden_top_level_imports(self):
        """Check for forbidden top-level module imports."""
        extra_forbidden = {"subprocess", "socket", "http"}
        violations = []
        for module_path in get_p02_modules():
            tree = ast.parse(module_path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_level = alias.name.split(".")[0]
                        if top_level in extra_forbidden:
                            violations.append(
                                f"{module_path.name}: import {alias.name}"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top_level = node.module.split(".")[0]
                        if top_level in extra_forbidden:
                            violations.append(
                                f"{module_path.name}: from {node.module}"
                            )
        assert not violations, f"Extra forbidden imports: {violations}"


class TestNoForbiddenOperations:
    def test_no_eval_or_exec(self):
        """P0.2 must not use eval, exec, or compile."""
        forbidden_calls = {"eval", "exec", "compile"}
        violations = []
        for module_path in get_p02_modules():
            tree = ast.parse(module_path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id in forbidden_calls:
                        violations.append(
                            f"{module_path.name}: {func.id}()"
                        )
        assert not violations, f"Forbidden calls: {violations}"

    def test_no_os_system(self):
        """P0.2 must not call os.system."""
        for module_path in get_p02_modules():
            tree = ast.parse(module_path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute) and func.attr == "system":
                        if isinstance(func.value, ast.Name) and func.value.id == "os":
                            pytest.fail(f"{module_path.name}: os.system() found")

    def test_no_subprocess_calls(self):
        """P0.2 must not call subprocess.run or subprocess.Popen."""
        for module_path in get_p02_modules():
            tree = ast.parse(module_path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute):
                        if (
                            isinstance(func.value, ast.Name)
                            and func.value.id == "subprocess"
                        ):
                            pytest.fail(
                                f"{module_path.name}: subprocess.{func.attr}() found"
                            )

    def test_no_network_calls(self):
        """P0.2 must not make network calls."""
        forbidden_attrs = {"socket", "connect", "request", "get", "post"}
        for module_path in get_p02_modules():
            content = module_path.read_text()
            for forbidden in ["urlopen", "requests.", "http.client", "socket.socket"]:
                if forbidden in content:
                    pytest.fail(
                        f"{module_path.name}: contains forbidden network pattern '{forbidden}'"
                    )

    def test_no_filesystem_writes(self):
        """P0.2 modules must not open files for writing."""
        for module_path in get_p02_modules():
            tree = ast.parse(module_path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "open":
                        # Check if 'w', 'a', or 'x' mode is used
                        if node.keywords:
                            for kw in node.keywords:
                                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                                    if kw.value.value in ("w", "a", "x", "w+", "a+"):
                                        pytest.fail(
                                            f"{module_path.name}: open() with write mode"
                                        )
                        elif len(node.args) >= 2:
                            mode_arg = node.args[1]
                            if isinstance(mode_arg, ast.Constant):
                                if mode_arg.value in ("w", "a", "x", "w+", "a+"):
                                    pytest.fail(
                                        f"{module_path.name}: open() with write mode"
                                    )

    def test_no_finalizers(self):
        """P0.2 must not define __del__, __weakref__, or finalizers."""
        forbidden_methods = {"__del__", "__weakref__"}
        for module_path in get_p02_modules():
            tree = ast.parse(module_path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in forbidden_methods:
                    pytest.fail(
                        f"{module_path.name}: defines forbidden method {node.name}"
                    )


class TestDepthLimit:
    """Gate 8 - Depth limit enforcement."""

    def test_depth_limit_blocks_grandchild_admission(self):
        from elpis_p0.expansion import (
            admit_expansion,
            SEMANTIC_SPACE,
            ABI_VERSION,
            SHAPE,
            DTYPE,
            VOCABULARY_SIZE,
            EXPANSION_TOKEN,
            VOID_TOKEN,
        )
        from elpis.contracts.budget import BudgetVector, Charge

        grid = [VOID_TOKEN] * 81
        grid[40] = EXPANSION_TOKEN
        grid = tuple(grid)

        # At depth 1, admission must be rejected by policy
        record = admit_expansion(
            request_id="depth-test",
            proposal_digest="pd1",
            proposed_cells=(40,),
            proposed_grid81=grid,
            semantic_space=SEMANTIC_SPACE,
            abi_version=ABI_VERSION,
            shape=SHAPE,
            dtype=DTYPE,
            vocabulary_size=VOCABULARY_SIZE,
            budget=BudgetVector(
                steps=10, depth=1, backend=None,
                tokens=None, energy=None, wall_ms=None, writes=None,
            ),
            spawn_cost=Charge(steps=1),
            allocation=Charge(steps=5),
            current_depth=1,
            frame_index=2,
        )
        assert record.decision == "REJECTED_POLICY"

    def test_depth_not_granted_still_blocks(self):
        """When depth axis is NOT_GRANTED, policy still blocks grandchildren."""
        from elpis_p0.expansion import (
            admit_expansion,
            SEMANTIC_SPACE,
            ABI_VERSION,
            SHAPE,
            DTYPE,
            VOCABULARY_SIZE,
            EXPANSION_TOKEN,
            VOID_TOKEN,
        )
        from elpis.contracts.budget import BudgetVector, Charge

        grid = [VOID_TOKEN] * 81
        grid[40] = EXPANSION_TOKEN
        grid = tuple(grid)

        # Depth NOT_GRANTED, steps granted
        budget = BudgetVector(
            steps=10, depth=None, backend=None,
            tokens=None, energy=None, wall_ms=None, writes=None,
        )
        record = admit_expansion(
            request_id="depth-ng",
            proposal_digest="pd1",
            proposed_cells=(40,),
            proposed_grid81=grid,
            semantic_space=SEMANTIC_SPACE,
            abi_version=ABI_VERSION,
            shape=SHAPE,
            dtype=DTYPE,
            vocabulary_size=VOCABULARY_SIZE,
            budget=budget,
            spawn_cost=Charge(steps=1),
            allocation=Charge(steps=5),
            current_depth=1,
            frame_index=2,
        )
        assert record.decision == "REJECTED_POLICY"
