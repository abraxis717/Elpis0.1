from __future__ import annotations

import ast
import contextlib
import hashlib
import inspect
import io
import json
import os
from pathlib import Path
import runpy
import sys
import threading
import time
import types
from typing import Any

C2R7C_R6_PROGRESS_V1 = True

HERE = Path(__file__).resolve().parent
PROBE = HERE / "source" / "redteam_c2r7c_residual_probe.py"
OVERLAY_P0 = HERE / "source" / "elpis_p0"
REPO = HERE.parent.parent
CANON_P0 = REPO / "components" / "Pipeline" / "P0ControlProtocol" / "src" / "elpis_p0"
CANON_SPINE = REPO / "components" / "TRMFractalSpine" / "src" / "elpis_fractal_spine"

PROHIBITED_GLOBAL_NAMES = {
    "schedule",
    "hidden_schedule",
    "target_grid",
    "expected_grid",
    "solution_grid",
    "final_grid",
    "answer_grid",
    "gold_grid",
    "ground_truth",
    "ground_truth_grid",
    "hidden_answer",
    "solution",
    "answer",
}

ALLOWED_MODULE_PREFIXES = {
    "builtins",
    "collections",
    "dataclasses",
    "functools",
    "hashlib",
    "heapq",
    "itertools",
    "json",
    "math",
    "operator",
    "random",
    "statistics",
    "typing",
    "elpis_p0",
}


class Poison:
    def __init__(self, name: str) -> None:
        self.name = name

    def _boom(self, *_: Any, **__: Any) -> Any:
        raise RuntimeError(f"PROHIBITED_HIDDEN_CAPABILITY_ACCESSED:{self.name}")

    __getattr__ = _boom
    __call__ = _boom
    __iter__ = _boom
    __len__ = _boom
    __bool__ = _boom
    __getitem__ = _boom
    __setitem__ = _boom
    __contains__ = _boom
    __eq__ = _boom
    __lt__ = _boom
    __le__ = _boom
    __gt__ = _boom
    __ge__ = _boom
    __hash__ = _boom
    __int__ = _boom
    __float__ = _boom
    __index__ = _boom
    __repr__ = lambda self: f"<Poison {self.name}>"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_package_stubs() -> None:
    p0_pkg = types.ModuleType("elpis_p0")
    p0_pkg.__path__ = [str(OVERLAY_P0), str(CANON_P0)]
    p0_pkg.__package__ = "elpis_p0"
    p0_pkg.__file__ = str(CANON_P0 / "__init__.py")
    sys.modules["elpis_p0"] = p0_pkg

    spine_pkg = types.ModuleType("elpis_fractal_spine")
    spine_pkg.__path__ = [str(CANON_SPINE)]
    spine_pkg.__package__ = "elpis_fractal_spine"
    spine_pkg.__file__ = str(CANON_SPINE / "__init__.py")
    sys.modules["elpis_fractal_spine"] = spine_pkg


def module_allowed(value: Any) -> bool:
    if not isinstance(value, types.ModuleType):
        return True
    name = value.__name__
    return any(name == p or name.startswith(p + ".") for p in ALLOWED_MODULE_PREFIXES)


def defined_in_probe(fn: Any, module_globals: dict[str, Any]) -> bool:
    return (
        inspect.isfunction(fn)
        and fn.__globals__ is module_globals
        and Path(inspect.getsourcefile(fn) or "").resolve() == PROBE.resolve()
    )


def collect_probe_closure(
    root_name: str,
    module_globals: dict[str, Any],
) -> tuple[set[str], dict[str, list[str]]]:
    seen: set[str] = set()
    graph: dict[str, list[str]] = {}
    todo = [root_name]
    while todo:
        name = todo.pop()
        if name in seen:
            continue
        obj = module_globals.get(name)
        if not inspect.isfunction(obj):
            raise RuntimeError(f"expected probe function {name!r}")
        seen.add(name)
        children: list[str] = []
        for ref in obj.__code__.co_names:
            candidate = module_globals.get(ref)
            if defined_in_probe(candidate, module_globals):
                children.append(ref)
                todo.append(ref)
        graph[name] = sorted(set(children))
    return seen, graph


def make_restricted_function(
    root_name: str,
    module_globals: dict[str, Any],
) -> tuple[Any, dict[str, Any], dict[str, list[str]]]:
    fn_names, graph = collect_probe_closure(root_name, module_globals)

    restricted: dict[str, Any] = {
        "__builtins__": __builtins__,
        "__name__": "elpis_c2r7c_capability_bound_search",
        "__package__": None,
    }

    # Plant explicit poison capabilities. A restricted function can only see
    # names present here; if code ever begins consulting one, R6 fails loudly.
    for name in sorted(PROHIBITED_GLOBAL_NAMES):
        restricted[name] = Poison(name)

    # Copy only globals actually referenced by the transitive probe functions.
    required_names: set[str] = set()
    for fn_name in fn_names:
        required_names.update(module_globals[fn_name].__code__.co_names)

    for name in sorted(required_names):
        if name in fn_names or name in PROHIBITED_GLOBAL_NAMES:
            continue
        if name not in module_globals:
            continue
        value = module_globals[name]
        if not module_allowed(value):
            raise RuntimeError(
                f"capability-bound search references unapproved module "
                f"{name}={getattr(value, '__name__', type(value).__name__)}"
            )
        restricted[name] = value

    # Clone the probe-local helper graph so those functions share only this
    # restricted global namespace.
    clones: dict[str, Any] = {}
    for name in fn_names:
        original = module_globals[name]
        clone = types.FunctionType(
            original.__code__,
            restricted,
            name=original.__name__,
            argdefs=original.__defaults__,
            closure=original.__closure__,
        )
        clone.__kwdefaults__ = getattr(original, "__kwdefaults__", None)
        clone.__annotations__ = dict(getattr(original, "__annotations__", {}))
        clones[name] = clone

    restricted.update(clones)

    root = clones[root_name]
    if root.__closure__:
        raise RuntimeError("refine_search unexpectedly carries a closure")

    return root, restricted, graph


def object_capability_scan(obj: Any, *, path: str = "arg", seen: set[int] | None = None) -> list[str]:
    if seen is None:
        seen = set()
    oid = id(obj)
    if oid in seen:
        return []
    seen.add(oid)

    hits: list[str] = []
    scalar = (str, bytes, int, float, bool, type(None))
    if isinstance(obj, scalar):
        return hits

    if isinstance(obj, dict):
        for k, v in obj.items():
            ks = str(k).lower()
            if ks in PROHIBITED_GLOBAL_NAMES:
                hits.append(f"{path}[{k!r}]")
            hits.extend(object_capability_scan(v, path=f"{path}[{k!r}]", seen=seen))
        return hits

    if isinstance(obj, (list, tuple, set, frozenset)):
        for i, item in enumerate(obj):
            hits.extend(object_capability_scan(item, path=f"{path}[{i}]", seen=seen))
        return hits

    if hasattr(obj, "__dict__"):
        for k, v in vars(obj).items():
            if k.lower() in PROHIBITED_GLOBAL_NAMES:
                hits.append(f"{path}.{k}")
            hits.extend(object_capability_scan(v, path=f"{path}.{k}", seen=seen))
    return hits


def main() -> None:
    install_package_stubs()

    # Import definitions without executing the campaign.
    ns = runpy.run_path(str(PROBE), run_name="elpis_c2r7c_probe_defs")

    if "refine_search" not in ns or "main" not in ns:
        raise SystemExit("probe does not expose refine_search/main")

    original_search = ns["refine_search"]
    restricted_search, restricted_globals, graph = make_restricted_function(
        "refine_search", ns
    )

    signature = inspect.signature(original_search)
    closure_vars = inspect.getclosurevars(original_search)
    prohibited_nonlocals = sorted(
        n for n in closure_vars.nonlocals if n.lower() in PROHIBITED_GLOBAL_NAMES
    )
    prohibited_globals = sorted(
        n for n in closure_vars.globals if n.lower() in PROHIBITED_GLOBAL_NAMES
    )
    if prohibited_nonlocals or prohibited_globals:
        raise SystemExit(
            "refine_search directly captures prohibited capability: "
            f"nonlocals={prohibited_nonlocals} globals={prohibited_globals}"
        )

    call_records: list[dict[str, Any]] = []
    progress_counts: dict[str, int] = {}

    def _run_with_progress(label: str, fn: Any, *args: Any, **kwargs: Any) -> Any:
        index = progress_counts.get(label, 0) + 1
        progress_counts[label] = index
        started = time.monotonic()
        done = threading.Event()

        print(
            f"R6_PROGRESS arm={label} case={index}/40 phase=begin",
            file=sys.stderr,
            flush=True,
        )

        def heartbeat() -> None:
            while not done.wait(5.0):
                elapsed = time.monotonic() - started
                print(
                    f"R6_HEARTBEAT arm={label} case={index}/40 "
                    f"elapsed_s={elapsed:.1f}",
                    file=sys.stderr,
                    flush=True,
                )

        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()
        try:
            return fn(*args, **kwargs)
        finally:
            done.set()
            elapsed = time.monotonic() - started
            print(
                f"R6_PROGRESS arm={label} case={index}/40 "
                f"phase=end elapsed_s={elapsed:.3f}",
                file=sys.stderr,
                flush=True,
            )

    def capability_guard(*args: Any, **kwargs: Any) -> Any:
        hits: list[str] = []
        for i, arg in enumerate(args):
            hits.extend(object_capability_scan(arg, path=f"arg[{i}]"))
        for name, value in kwargs.items():
            hits.extend(object_capability_scan(value, path=f"kw[{name}]"))
        if hits:
            raise RuntimeError(
                "PROHIBITED_CAPABILITY_PRESENT_IN_CALL:" + ",".join(sorted(set(hits)))
            )

        result = _run_with_progress(
            "search", restricted_search, *args, **kwargs
        )
        call_records.append(
            {
                "argc": len(args),
                "kwarg_names": sorted(kwargs),
                "arg_types": [type(x).__name__ for x in args],
            }
        )
        return result

    # The returned runpy namespace is the main function's global dictionary in
    # CPython. Replace only the search arm; all fixture generation and controls
    # remain Claude's original code.
    main_fn = ns["main"]
    main_globals = main_fn.__globals__
    if main_globals.get("refine_search") is not original_search:
        raise SystemExit("unexpected runpy global identity")
    main_globals["refine_search"] = capability_guard

    for _arm_name in ("refine_null", "refine_shadow", "refine_random"):
        _original = main_globals[_arm_name]

        def _make_wrapper(name: str, fn: Any) -> Any:
            def _wrapped(*args: Any, **kwargs: Any) -> Any:
                return _run_with_progress(
                    name.removeprefix("refine_"), fn, *args, **kwargs
                )
            return _wrapped

        main_globals[_arm_name] = _make_wrapper(_arm_name, _original)

    print(
        "R6_PROGRESS campaign=40_cases phase=begin",
        file=sys.stderr,
        flush=True,
    )

    # Poison hidden-answer-looking module globals as an additional dynamic tripwire.
    prior = {}
    for name in PROHIBITED_GLOBAL_NAMES:
        prior[name] = main_globals.get(name, None)
        main_globals[name] = Poison(name)

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            retval = main_fn()
    finally:
        # No later code depends on this namespace, but restore for clean semantics.
        for name, value in prior.items():
            if value is None:
                main_globals.pop(name, None)
            else:
                main_globals[name] = value

    print(
        "R6_PROGRESS campaign=40_cases phase=end",
        file=sys.stderr,
        flush=True,
    )

    text = buf.getvalue().strip()
    if not text:
        raise SystemExit("probe main produced no JSON")
    payload = json.loads(text)

    summary = payload.get("summary", {})
    search = summary.get("search", {})
    random_arm = summary.get("random", {})
    null_arm = summary.get("null", {})
    shadow = summary.get("shadow", {})

    search_resolved = int(search.get("resolved", -1))
    search_total = int(search.get("total", -1))
    search_auth = int(search.get("authority_violations", -1))

    # Exact baseline from the preceding R4 campaign.
    baseline_match = (
        search_resolved == 39
        and search_total == 40
        and search_auth == 0
        and int(random_arm.get("resolved", -1)) == 2
        and int(null_arm.get("resolved", -1)) == 0
        and int(shadow.get("resolved", -1)) == 0
    )

    report = {
        "schema": "elpis.c2r7c.capability-bound-search.v1",
        "role": "EXPERIMENT_ONLY_DYNAMIC_CAUSALITY_PROBE",
        "probe_sha256": sha256(PROBE),
        "refine_search_signature": str(signature),
        "probe_local_call_graph": graph,
        "restricted_global_names": sorted(restricted_globals),
        "prohibited_capability_names": sorted(PROHIBITED_GLOBAL_NAMES),
        "prohibited_direct_globals": prohibited_globals,
        "prohibited_nonlocals": prohibited_nonlocals,
        "search_calls_observed": len(call_records),
        "search_call_shapes": sorted(
            {json.dumps(r, sort_keys=True) for r in call_records}
        ),
        "summary": summary,
        "baseline_exact_match": baseline_match,
        "verdict": (
            "PASS_CAPABILITY_BOUND_SEARCH_REPRODUCES_BASELINE"
            if baseline_match and len(call_records) == 40
            else "FAIL_OR_REVIEW"
        ),
        "claim": (
            "The search control reproduced the prior 39/40 result after being "
            "cloned into a restricted global namespace and dynamically denied "
            "hidden-answer-looking capabilities. This is mechanism evidence "
            "against answer leakage; it is not evidence that the TRM itself can "
            "perform the refinement."
        ),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
