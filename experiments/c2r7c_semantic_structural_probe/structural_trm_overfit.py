"""TRM-0 microscopic overfit test.

Purpose:
    Test whether the experimental structural TRM can learn the 218
    capability-clean teacher transitions already extracted from C2R7-C.

This is NOT a generalization test and NOT qualification evidence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import time

import torch
import torch.nn.functional as F

from structural_trm_features import FEATURE_WIDTH
from structural_trm_model import EDIT_VOCAB, StructuralTRM64


GRID_SIZE = 81
VOCAB = 10


def load_dataset(path: Path):
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if not rows:
        raise RuntimeError("empty dataset")

    grids = []
    masks = []
    declared = []
    residual = []
    targets = []

    input_to_target = {}
    conflicting_targets = 0
    duplicate_inputs = 0

    for row in rows:
        if row.get("schema") != "elpis.c2r7c.trm0.training-transition.v1":
            raise RuntimeError("unexpected dataset schema")

        if row["cost_after"] >= row["cost_before"]:
            raise RuntimeError("non-improving teacher transition")

        grid = tuple(int(v) for v in row["grid81"])
        mask = tuple(int(v) for v in row["writable_mask81"])
        target = tuple(int(v) for v in row["next_grid81"])

        if len(grid) != GRID_SIZE or len(mask) != GRID_SIZE or len(target) != GRID_SIZE:
            raise RuntimeError("invalid Grid81 shape")

        d_idx = tuple(int(v) for v in row["declared_indices529"])
        r_idx = tuple(int(v) for v in row["residual_indices529"])

        d = [0.0] * FEATURE_WIDTH
        r = [0.0] * FEATURE_WIDTH

        for index in d_idx:
            d[index] = 1.0

        for index in r_idx:
            r[index] = 1.0

        key = (grid, mask, d_idx, r_idx)

        previous = input_to_target.get(key)
        if previous is not None:
            duplicate_inputs += 1
            if previous != target:
                conflicting_targets += 1
        else:
            input_to_target[key] = target

        grids.append(grid)
        masks.append(mask)
        declared.append(d)
        residual.append(r)
        targets.append(target)

    if conflicting_targets:
        raise RuntimeError(
            f"teacher mapping has {conflicting_targets} conflicting duplicate inputs"
        )

    x = torch.tensor(grids, dtype=torch.long)
    m = torch.tensor(masks, dtype=torch.long)
    d = torch.tensor(declared, dtype=torch.float32)
    r = torch.tensor(residual, dtype=torch.float32)
    y = torch.tensor(targets, dtype=torch.long)

    changed = (x != y) & m.bool()

    if not torch.all(changed.any(dim=1)):
        raise RuntimeError("dataset contains identity transition")

    frozen_changed = (x != y) & (~m.bool())
    if frozen_changed.any():
        raise RuntimeError("teacher changed frozen locus")

    return {
        "rows": rows,
        "grid": x,
        "mask": m,
        "declared": d,
        "residual": r,
        "target": y,
        "duplicate_inputs": duplicate_inputs,
        "conflicting_targets": conflicting_targets,
        "changed_loci": int(changed.sum().item()),
    }


@torch.no_grad()
def evaluate(model, data):
    model.eval()

    x = data["grid"]
    m = data["mask"]
    d = data["declared"]
    r = data["residual"]
    y = data["target"]

    _, output = model(x, m, d, r)

    action = output["edit_logits"].argmax(dim=-1)
    should_edit = m.bool() & action.ne(0)
    replacement = (action - 1).clamp_min(0)

    proposal = torch.where(
        should_edit,
        replacement,
        x,
    )

    changed = (x != y) & m.bool()
    stable = (x == y) & m.bool()

    change_correct = (
        proposal[changed] == y[changed]
    ).float().mean().item()

    stable_correct = (
        proposal[stable] == y[stable]
    ).float().mean().item()

    exact = (
        proposal == y
    ).all(dim=1)

    frozen_ok = torch.equal(
        proposal[~m.bool()],
        x[~m.bool()],
    )

    return {
        "change_acc": change_correct,
        "stable_acc": stable_correct,
        "exact": int(exact.sum().item()),
        "total": int(x.shape[0]),
        "frozen_ok": frozen_ok,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--batch", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=20260826)
    args = parser.parse_args()

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(4)

    data = load_dataset(args.data)

    print(
        "TRM0_OVERFIT_DATA "
        f"examples={len(data['rows'])} "
        f"changed_loci={data['changed_loci']} "
        f"duplicate_inputs={data['duplicate_inputs']} "
        f"conflicting_targets={data['conflicting_targets']}",
        flush=True,
    )

    model = StructuralTRM64(
        h_cycles=1,
        l_cycles=2,
    )

    params = sum(
        p.numel()
        for p in model.parameters()
    )

    print(
        "TRM0_OVERFIT_MODEL "
        f"params={params} hidden=64 "
        "h_cycles=1 l_cycles=2 "
        "note=reduced_compute_overfit_smoke",
        flush=True,
    )

    initial = evaluate(model, data)

    print(
        "TRM0_OVERFIT_INITIAL "
        f"change_acc={initial['change_acc']:.4f} "
        f"stable_acc={initial['stable_acc']:.4f} "
        f"exact={initial['exact']}/{initial['total']} "
        f"frozen_ok={initial['frozen_ok']}",
        flush=True,
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=1e-4,
    )

    x = data["grid"]
    m = data["mask"]
    d = data["declared"]
    r = data["residual"]
    y = data["target"]

    n = x.shape[0]
    started = time.monotonic()

    import copy

    best_exact = 0
    best_change = 0.0
    best_stable = 0.0
    best_state = copy.deepcopy(model.state_dict())

    for epoch in range(1, args.epochs + 1):
        epoch_started = time.monotonic()
        model.train()

        permutation = torch.randperm(n)
        running_loss = 0.0
        batches = 0

        for start in range(0, n, args.batch):
            indices = permutation[start:start + args.batch]

            bx = x[indices]
            bm = m[indices]
            bd = d[indices]
            br = r[indices]
            by = y[indices]

            optimizer.zero_grad(set_to_none=True)

            _, output = model(
                bx,
                bm,
                bd,
                br,
            )

            edit_logits = output["edit_logits"]

            writable = bm.bool()
            changed = (bx != by) & writable
            stable = (bx == by) & writable

            edit_target = torch.zeros_like(by)
            edit_target[changed] = by[changed] + 1

            edit_loss = F.cross_entropy(
                edit_logits.reshape(-1, EDIT_VOCAB),
                edit_target.reshape(-1),
                reduction="none",
            ).reshape_as(by)

            weights = torch.zeros_like(
                edit_loss
            )

            weights[stable] = 1.0
            weights[changed] = 12.0

            loss = (
                edit_loss * weights
            ).sum() / weights.sum().clamp_min(1.0)

            loss.backward()

            torch.nn.utils.clip_grad_norm_(
                model.parameters(),
                1.0,
            )

            optimizer.step()

            running_loss += float(loss.item())
            batches += 1

        metrics = evaluate(model, data)

        improved = (
            metrics["exact"] > best_exact
            or (
                metrics["exact"] == best_exact
                and metrics["change_acc"] > best_change
            )
            or (
                metrics["exact"] == best_exact
                and metrics["change_acc"] == best_change
                and metrics["stable_acc"] > best_stable
            )
        )

        if improved:
            best_exact = metrics["exact"]
            best_change = metrics["change_acc"]
            best_stable = metrics["stable_acc"]
            best_state = copy.deepcopy(model.state_dict())

        elapsed_epoch = time.monotonic() - epoch_started

        if (
            epoch <= 5
            or epoch % 10 == 0
            or improved
            or epoch == args.epochs
        ):
            print(
                f"TRM0_OVERFIT epoch={epoch:03d}/{args.epochs} "
                f"loss={running_loss / max(1, batches):.5f} "
                f"change_acc={metrics['change_acc']:.4f} "
                f"stable_acc={metrics['stable_acc']:.4f} "
                f"exact={metrics['exact']}/{metrics['total']} "
                f"best={best_exact}/{metrics['total']} "
                f"epoch_s={elapsed_epoch:.2f}",
                flush=True,
            )

        if (
            metrics["exact"] == metrics["total"]
            and metrics["change_acc"] == 1.0
            and metrics["stable_acc"] == 1.0
            and metrics["frozen_ok"]
        ):
            print(
                f"TRM0_OVERFIT_EARLY_STOP epoch={epoch}",
                flush=True,
            )
            break

    model.load_state_dict(best_state)
    final = evaluate(model, data)
    elapsed = time.monotonic() - started

    passed = (
        final["change_acc"] >= 0.99
        and final["stable_acc"] >= 0.99
        and (final["exact"] / final["total"]) >= 0.95
        and final["frozen_ok"]
    )

    print(
        "TRM0_OVERFIT_FINAL "
        f"verdict={'PASS' if passed else 'FAIL'} "
        f"change_acc={final['change_acc']:.4f} "
        f"stable_acc={final['stable_acc']:.4f} "
        f"exact={final['exact']}/{final['total']} "
        f"best_exact={best_exact}/{final['total']} "
        f"best_change_acc={best_change:.4f} "
        f"frozen_ok={final['frozen_ok']} "
        f"elapsed_s={elapsed:.2f}",
        flush=True,
    )

    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
