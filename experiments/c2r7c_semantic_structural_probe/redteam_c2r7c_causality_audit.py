from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable

HERE = Path(__file__).resolve().parent
PROBE = HERE / "source" / "redteam_c2r7c_residual_probe.py"
RESIDUAL = HERE / "source" / "elpis_p0" / "structural_residual.py"

SUSPICIOUS = re.compile(
    r"(target|expected|answer|oracle|solution|gold|truth|ground|hidden|"
    r"desired|goal|final[_a-z]*grid|resolved[_a-z]*grid|reference[_a-z]*grid)",
    re.IGNORECASE,
)
SEARCH_ROOT = re.compile(r"(search|solve|refin)", re.IGNORECASE)
RESIDUAL_ROOT = re.compile(r"(residual|coher|invariant|validat|score|halt)", re.IGNORECASE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def qname(stack: list[str], name: str) -> str:
    return ".".join([*stack, name]) if stack else name


class Analyzer(ast.NodeVisitor):
    def __init__(self, source: str) -> None:
        self.source = source
        self.stack: list[str] = []
        self.defs: dict[str, ast.AST] = {}
        self.calls: dict[str, set[str]] = {}
        self.refs: dict[str, list[dict[str, object]]] = {}
        self.params: dict[str, list[str]] = {}
        self.current: str | None = None

    def _enter(self, node: ast.AST, name: str, args: ast.arguments | None = None) -> None:
        full = qname(self.stack, name)
        self.defs[full] = node
        self.calls.setdefault(full, set())
        self.refs.setdefault(full, [])
        if args is not None:
            params = []
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                params.append(arg.arg)
            if args.vararg:
                params.append(args.vararg.arg)
            if args.kwarg:
                params.append(args.kwarg.arg)
            self.params[full] = params
        previous = self.current
        self.current = full
        self.stack.append(name)
        for child in ast.iter_child_nodes(node):
            # Avoid recursively re-entering nested defs through generic walk.
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.visit(child)
            else:
                self.visit(child)
        self.stack.pop()
        self.current = previous

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._enter(node, node.name, node.args)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._enter(node, node.name, node.args)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._enter(node, node.name, None)

    def visit_Call(self, node: ast.Call) -> None:
        if self.current:
            called = None
            if isinstance(node.func, ast.Name):
                called = node.func.id
            elif isinstance(node.func, ast.Attribute):
                called = node.func.attr
            if called:
                self.calls.setdefault(self.current, set()).add(called)
        self.generic_visit(node)

    def _record_ref(self, token: str, node: ast.AST) -> None:
        if not self.current or not SUSPICIOUS.search(token):
            return
        line = getattr(node, "lineno", None)
        text = ""
        if isinstance(line, int):
            lines = self.source.splitlines()
            if 1 <= line <= len(lines):
                text = lines[line - 1].strip()
        self.refs.setdefault(self.current, []).append(
            {"token": token, "line": line, "text": text[:240]}
        )

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self._record_ref(node.id, node)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._record_ref(node.attr, node)
        self.generic_visit(node)


def analyze(path: Path) -> dict[str, object]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    a = Analyzer(source)
    # Top-level defs need ordinary visitor entry.
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            a.visit(node)

    simple_to_qualified: dict[str, set[str]] = {}
    for full in a.defs:
        simple_to_qualified.setdefault(full.rsplit(".", 1)[-1], set()).add(full)

    def reachable(roots: Iterable[str]) -> set[str]:
        seen: set[str] = set()
        todo = list(roots)
        while todo:
            cur = todo.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for called_simple in a.calls.get(cur, set()):
                for nxt in simple_to_qualified.get(called_simple, set()):
                    if nxt not in seen:
                        todo.append(nxt)
        return seen

    search_roots = sorted(n for n in a.defs if SEARCH_ROOT.search(n))
    residual_roots = sorted(n for n in a.defs if RESIDUAL_ROOT.search(n))
    search_reachable = reachable(search_roots)
    residual_reachable = reachable(residual_roots)

    suspicious_params = {
        name: [p for p in a.params.get(name, []) if SUSPICIOUS.search(p)]
        for name in a.params
        if any(SUSPICIOUS.search(p) for p in a.params.get(name, []))
    }

    reachable_refs = []
    for name in sorted(search_reachable):
        for ref in a.refs.get(name, []):
            reachable_refs.append({"function": name, **ref})

    all_refs = []
    for name in sorted(a.refs):
        for ref in a.refs[name]:
            all_refs.append({"function": name, **ref})

    return {
        "path": str(path),
        "sha256": sha256(path),
        "definitions": len(a.defs),
        "search_roots": search_roots,
        "residual_roots": residual_roots,
        "search_reachable_count": len(search_reachable),
        "search_reachable": sorted(search_reachable),
        "suspicious_parameters": suspicious_params,
        "search_reachable_suspicious_refs": reachable_refs,
        "all_suspicious_refs": all_refs,
        "static_target_path_status": (
            "NO_STATIC_TARGET_PATH_FOUND"
            if search_roots and not reachable_refs and not suspicious_params
            else "REVIEW_REQUIRED"
        ),
    }


def lexical_hits(path: Path) -> list[dict[str, object]]:
    hits = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if SUSPICIOUS.search(line):
            hits.append({"line": number, "text": line.strip()[:260]})
    return hits


def main() -> None:
    for path in (PROBE, RESIDUAL):
        if not path.is_file():
            raise SystemExit(f"missing source: {path}")

    probe = analyze(PROBE)
    residual = analyze(RESIDUAL)

    # This is intentionally conservative. "NO_STATIC_TARGET_PATH_FOUND" is
    # evidence against obvious answer leakage, not a semantic proof.
    search_status = probe["static_target_path_status"]
    residual_status = residual["static_target_path_status"]
    overall = (
        "PASS_NO_OBVIOUS_HIDDEN_TARGET_PATH"
        if search_status == "NO_STATIC_TARGET_PATH_FOUND"
        and residual_status == "NO_STATIC_TARGET_PATH_FOUND"
        else "REVIEW_REQUIRED"
    )

    report = {
        "schema": "elpis.c2r7c.causality-audit.v1",
        "role": "EXPERIMENT_ONLY_STATIC_CAUSALITY_AUDIT",
        "overall": overall,
        "interpretation": (
            "Static absence of an answer path is necessary but not sufficient. "
            "A later capability-bound dynamic test must still prove the search "
            "refiner can run with only initial structural state, writable scope, "
            "declared invariants, and capacity metadata."
        ),
        "probe": probe,
        "residual": residual,
        "lexical_target_hits": {
            "probe": lexical_hits(PROBE),
            "residual": lexical_hits(RESIDUAL),
        },
    }

    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
