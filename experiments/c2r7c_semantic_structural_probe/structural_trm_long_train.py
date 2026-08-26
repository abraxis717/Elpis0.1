"""Long offline TRM-0 structural refinement training.

Purpose:
    Drive the 64-wide sparse-edit StructuralTRM through a long full-recursion
    overfit campaign on the capability-clean C2R7-C teacher transitions.

This remains an overfit/mechanism experiment, not held-out qualification.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import random
import time

import torch
import torch.nn.functional as F

from structural_trm_model import (
    EDIT_VOCAB,
    StructuralTRM64,
)
from structural_trm_overfit import (
    evaluate,
    load_dataset,
)


DEFAULT_DATA = Path(
    "/Users/abraxis/Elpis/Elpis_Qualification/work/"
    "C2R7C_TRM0_DATASET_SMOKE.jsonl"
)

DEFAULT_RUN_DIR = Path(
    "/Users/abraxis/Elpis/Elpis_Qualification/work/"
    "C2R7C_TRM0_LONG"
)


def save_checkpoint(
    path,
    *,
    model,
    optimizer,
    scheduler,
    epoch,
    best,
    config,
):
    tmp = path.with_suffix(path.suffix + ".tmp")

    torch.save(
        {
            "schema": "elpis.c2r7c.trm0.long-train.v1",
            "epoch": epoch,
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "scheduler_state": scheduler.state_dict(),
            "best": best,
            "config": config,
        },
        tmp,
    )

    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="trm-long-train"
    )

    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA,
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=DEFAULT_RUN_DIR,
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=2000,
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=64,
    )
    parser.add_argument(
        "--lr",
        type=float,
        default=7e-4,
    )
    parser.add_argument(
        "--eta-min",
        type=float,
        default=5e-5,
    )
    parser.add_argument(
        "--changed-weight",
        type=float,
        default=8.0,
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
    )
    parser.add_argument(
        "--eval-every",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--save-every",
        type=int,
        default=50,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260826,
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
    )

    args = parser.parse_args()

    args.run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)

    data = load_dataset(args.data)

    x = data["grid"]
    mask = data["mask"]
    declared = data["declared"]
    residual = data["residual"]
    target = data["target"]

    model = StructuralTRM64(
        h_cycles=3,
        l_cycles=6,
    )

    params = sum(
        parameter.numel()
        for parameter in model.parameters()
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=1e-4,
    )

    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=args.epochs,
        eta_min=args.eta_min,
    )

    config = {
        "epochs": args.epochs,
        "batch": args.batch,
        "initial_lr": args.lr,
        "eta_min": args.eta_min,
        "changed_weight": args.changed_weight,
        "threads": args.threads,
        "h_cycles": 3,
        "l_cycles": 6,
        "hidden": 64,
        "parameters": params,
        "examples": int(x.shape[0]),
    }

    latest_path = args.run_dir / "latest.pt"
    best_path = args.run_dir / "best.pt"
    summary_path = args.run_dir / "summary.json"

    best = {
        "exact": 0,
        "change_acc": 0.0,
        "stable_acc": 0.0,
        "epoch": 0,
    }

    start_epoch = 1

    if latest_path.exists() and not args.fresh:
        checkpoint = torch.load(
            latest_path,
            map_location="cpu",
        )

        model.load_state_dict(
            checkpoint["model_state"]
        )
        optimizer.load_state_dict(
            checkpoint["optimizer_state"]
        )
        scheduler.load_state_dict(
            checkpoint["scheduler_state"]
        )

        best = dict(checkpoint["best"])
        start_epoch = int(
            checkpoint["epoch"]
        ) + 1

        print(
            "TRM_LONG_RESUME "
            f"from_epoch={start_epoch} "
            f"best_exact={best['exact']}/{x.shape[0]} "
            f"best_epoch={best['epoch']}",
            flush=True,
        )

    initial = evaluate(model, data)

    print(
        "TRM_LONG_BEGIN "
        f"examples={x.shape[0]} "
        f"params={params} "
        "hidden=64 "
        "h_cycles=3 "
        "l_cycles=6 "
        f"epochs={args.epochs} "
        f"start_epoch={start_epoch} "
        f"threads={args.threads}",
        flush=True,
    )

    print(
        "TRM_LONG_INITIAL "
        f"change_acc={initial['change_acc']:.4f} "
        f"stable_acc={initial['stable_acc']:.4f} "
        f"exact={initial['exact']}/{initial['total']} "
        f"frozen_ok={initial['frozen_ok']}",
        flush=True,
    )

    n = x.shape[0]
    run_started = time.monotonic()
    recent_epoch_seconds = []

    current_epoch = start_epoch - 1

    try:
        for epoch in range(
            start_epoch,
            args.epochs + 1,
        ):
            current_epoch = epoch
            epoch_started = time.monotonic()

            model.train()

            permutation = torch.randperm(n)

            running_loss = 0.0
            batch_count = 0

            for start in range(
                0,
                n,
                args.batch,
            ):
                index = permutation[
                    start:start + args.batch
                ]

                bx = x[index]
                bm = mask[index]
                bd = declared[index]
                br = residual[index]
                by = target[index]

                optimizer.zero_grad(
                    set_to_none=True
                )

                _, output = model(
                    bx,
                    bm,
                    bd,
                    br,
                )

                logits = output[
                    "edit_logits"
                ]

                writable = bm.bool()
                changed = (
                    (bx != by)
                    & writable
                )
                stable = (
                    (bx == by)
                    & writable
                )

                edit_target = torch.zeros_like(
                    by
                )

                edit_target[changed] = (
                    by[changed] + 1
                )

                cell_loss = F.cross_entropy(
                    logits.reshape(
                        -1,
                        EDIT_VOCAB,
                    ),
                    edit_target.reshape(-1),
                    reduction="none",
                ).reshape_as(by)

                weights = torch.zeros_like(
                    cell_loss
                )

                weights[stable] = 1.0
                weights[changed] = (
                    args.changed_weight
                )

                loss = (
                    cell_loss * weights
                ).sum() / weights.sum().clamp_min(
                    1.0
                )

                loss.backward()

                torch.nn.utils.clip_grad_norm_(
                    model.parameters(),
                    1.0,
                )

                optimizer.step()

                running_loss += float(
                    loss.item()
                )
                batch_count += 1

            scheduler.step()

            epoch_seconds = (
                time.monotonic()
                - epoch_started
            )

            recent_epoch_seconds.append(
                epoch_seconds
            )

            if len(recent_epoch_seconds) > 20:
                recent_epoch_seconds.pop(0)

            should_eval = (
                epoch <= 5
                or epoch % args.eval_every == 0
                or epoch == args.epochs
            )

            metrics = None
            improved = False

            if should_eval:
                metrics = evaluate(
                    model,
                    data,
                )

                candidate = (
                    metrics["exact"],
                    metrics["change_acc"],
                    metrics["stable_acc"],
                )

                incumbent = (
                    best["exact"],
                    best["change_acc"],
                    best["stable_acc"],
                )

                if candidate > incumbent:
                    improved = True

                    best = {
                        "exact": int(
                            metrics["exact"]
                        ),
                        "change_acc": float(
                            metrics["change_acc"]
                        ),
                        "stable_acc": float(
                            metrics["stable_acc"]
                        ),
                        "epoch": epoch,
                    }

                    save_checkpoint(
                        best_path,
                        model=model,
                        optimizer=optimizer,
                        scheduler=scheduler,
                        epoch=epoch,
                        best=best,
                        config=config,
                    )

            if (
                epoch % args.save_every == 0
                or epoch == args.epochs
            ):
                save_checkpoint(
                    latest_path,
                    model=model,
                    optimizer=optimizer,
                    scheduler=scheduler,
                    epoch=epoch,
                    best=best,
                    config=config,
                )

            if (
                epoch <= 5
                or epoch % 10 == 0
                or improved
                or epoch == args.epochs
            ):
                mean_epoch = sum(
                    recent_epoch_seconds
                ) / len(recent_epoch_seconds)

                remaining = (
                    args.epochs - epoch
                ) * mean_epoch

                lr = optimizer.param_groups[
                    0
                ]["lr"]

                status = (
                    f"TRM_LONG epoch="
                    f"{epoch:04d}/{args.epochs} "
                    f"loss="
                    f"{running_loss / max(batch_count, 1):.6f} "
                    f"lr={lr:.8f} "
                    f"epoch_s={epoch_seconds:.2f} "
                    f"eta_min={remaining / 60.0:.1f}"
                )

                if metrics is not None:
                    status += (
                        f" change_acc="
                        f"{metrics['change_acc']:.4f}"
                        f" stable_acc="
                        f"{metrics['stable_acc']:.4f}"
                        f" exact="
                        f"{metrics['exact']}/{metrics['total']}"
                    )

                status += (
                    f" best="
                    f"{best['exact']}/{n}"
                    f"@{best['epoch']}"
                )

                print(
                    status,
                    flush=True,
                )

            if (
                metrics is not None
                and metrics["exact"]
                == metrics["total"]
                and metrics["change_acc"] == 1.0
                and metrics["stable_acc"] == 1.0
                and metrics["frozen_ok"]
            ):
                print(
                    "TRM_LONG_PERFECT "
                    f"epoch={epoch} "
                    f"exact={metrics['exact']}/"
                    f"{metrics['total']}",
                    flush=True,
                )

                save_checkpoint(
                    latest_path,
                    model=model,
                    optimizer=optimizer,
                    scheduler=scheduler,
                    epoch=epoch,
                    best=best,
                    config=config,
                )

                break

    except KeyboardInterrupt:
        print(
            "\nTRM_LONG_INTERRUPT "
            f"epoch={current_epoch} "
            "saving_latest=YES",
            flush=True,
        )

        save_checkpoint(
            latest_path,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
            epoch=current_epoch,
            best=best,
            config=config,
        )

        return 130

    if best_path.exists():
        checkpoint = torch.load(
            best_path,
            map_location="cpu",
        )

        model.load_state_dict(
            checkpoint["model_state"]
        )

    final = evaluate(
        model,
        data,
    )

    exact_ratio = (
        final["exact"]
        / final["total"]
    )

    passed = (
        final["change_acc"] >= 0.99
        and final["stable_acc"] >= 0.99
        and exact_ratio >= 0.95
        and final["frozen_ok"]
    )

    elapsed = (
        time.monotonic()
        - run_started
    )

    summary = {
        "schema": (
            "elpis.c2r7c.trm0."
            "long-train-summary.v1"
        ),
        "verdict": (
            "PASS"
            if passed
            else "FAIL"
        ),
        "best": best,
        "final": final,
        "exact_ratio": exact_ratio,
        "elapsed_s": elapsed,
        "config": config,
        "best_checkpoint": str(
            best_path
        ),
        "latest_checkpoint": str(
            latest_path
        ),
    }

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "TRM_LONG_FINAL "
        f"verdict="
        f"{'PASS' if passed else 'FAIL'} "
        f"change_acc="
        f"{final['change_acc']:.4f} "
        f"stable_acc="
        f"{final['stable_acc']:.4f} "
        f"exact="
        f"{final['exact']}/{final['total']} "
        f"exact_ratio={exact_ratio:.6f} "
        f"best="
        f"{best['exact']}/{n}"
        f"@{best['epoch']} "
        f"frozen_ok={final['frozen_ok']} "
        f"elapsed_min={elapsed / 60.0:.1f}",
        flush=True,
    )

    print(
        f"BEST_CHECKPOINT={best_path}",
        flush=True,
    )
    print(
        f"SUMMARY={summary_path}",
        flush=True,
    )

    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
