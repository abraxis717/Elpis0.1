from __future__ import annotations

import argparse
import json
from pathlib import Path

from .model import default_cache_dir, fetch_model, verify_model
from .refinement import solve_sudoku
from .sudoku import format_grid, parse_puzzle


def _model_fetch(args: argparse.Namespace) -> int:
    path = fetch_model(cache_dir=Path(args.cache_dir) if args.cache_dir else None, force=args.force)
    info = verify_model(path)
    print(json.dumps(info, indent=2, sort_keys=True))
    return 0


def _model_verify(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else default_cache_dir() / "model.safetensors"
    print(json.dumps(verify_model(path), indent=2, sort_keys=True))
    return 0


def _sudoku_solve(args: argparse.Namespace) -> int:
    puzzle_text = Path(args.file).read_text(encoding="utf-8") if args.file else args.puzzle
    puzzle = parse_puzzle(puzzle_text)
    result = solve_sudoku(
        puzzle,
        model_path=Path(args.model) if args.model else None,
        device=args.device,
        max_steps=args.max_steps,
    )
    payload = {
        "status": result.status,
        "device": result.device,
        "steps": [
            {
                "step": item.step,
                "valid": item.valid,
                "complete": item.complete,
                "conflicts": list(item.conflicts),
            }
            for item in result.steps
        ],
        "solution": format_grid(result.solution) if result.solution else None,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.status == "SOLVED" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="elpis", description="Runnable Elpis reference runtime")
    sub = parser.add_subparsers(dest="command", required=True)

    model = sub.add_parser("model", help="manage the pinned TRM checkpoint")
    model_sub = model.add_subparsers(dest="model_command", required=True)
    fetch = model_sub.add_parser("fetch", help="download, verify and convert the pinned checkpoint")
    fetch.add_argument("--cache-dir")
    fetch.add_argument("--force", action="store_true")
    fetch.set_defaults(func=_model_fetch)
    verify = model_sub.add_parser("verify", help="verify a converted safetensors checkpoint")
    verify.add_argument("--path")
    verify.set_defaults(func=_model_verify)

    sudoku = sub.add_parser("sudoku", help="Sudoku reference task")
    sudoku_sub = sudoku.add_subparsers(dest="sudoku_command", required=True)
    solve = sudoku_sub.add_parser("solve", help="run bounded TRM refinement")
    source = solve.add_mutually_exclusive_group(required=True)
    source.add_argument("--puzzle", help="81 characters; 0 or . means blank")
    source.add_argument("--file", help="text file containing an 81-cell puzzle")
    solve.add_argument("--model", help="path to converted model.safetensors")
    solve.add_argument("--device", default="auto", help="auto, cpu, cuda, mps")
    solve.add_argument("--max-steps", type=int, default=16)
    solve.set_defaults(func=_sudoku_solve)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args))
