from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import venv


REPO = Path(__file__).resolve().parent.parent
SRC = REPO / "src"
sys.path.insert(0, str(SRC))

from elpis_reference.platform_setup import (  # noqa: E402
    build_plan,
    detect_platform,
    native_build_commands,
)


def _venv_python(root: Path) -> Path:
    if sys.platform == "win32":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Platform-aware Elpis bootstrap"
    )
    parser.add_argument(
        "--profile",
        choices=("reference", "full"),
        default="reference",
    )
    parser.add_argument(
        "--native",
        choices=("auto", "on", "off"),
        default="auto",
    )
    parser.add_argument(
        "--venv",
        default=".venv",
    )
    parser.add_argument(
        "--build-dir",
        default=".elpis-build",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
    )
    args = parser.parse_args()

    detected = detect_platform()
    plan = build_plan(
        args.profile,
        native=args.native,
        detected=detected,
    )

    print(
        json.dumps(
            {
                "platform": detected.to_dict(),
                "plan": plan.to_dict(),
                "venv": str((REPO / args.venv).resolve()),
                "build_dir": str((REPO / args.build_dir).resolve()),
            },
            indent=2,
            sort_keys=True,
        )
    )

    if args.dry_run:
        return 0

    venv_root = (REPO / args.venv).resolve()
    venv.EnvBuilder(
        with_pip=True,
        clear=False,
    ).create(venv_root)

    python = _venv_python(venv_root)

    subprocess.run(
        [str(python), "-m", "pip", "install", "--upgrade", "pip"],
        check=True,
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", plan.package_spec],
        cwd=REPO,
        check=True,
    )

    if plan.build_native_hacf:
        for command in native_build_commands(
            REPO,
            REPO / args.build_dir,
        ):
            subprocess.run(
                list(command),
                cwd=REPO,
                check=True,
            )

    elpis_executable = (
        venv_root / "Scripts" / "elpis.exe"
        if sys.platform == "win32"
        else venv_root / "bin" / "elpis"
    )

    print(
        json.dumps(
            {
                "status": "INSTALLED",
                "python": str(python),
                "elpis": str(elpis_executable),
                "profile": plan.profile,
                "device_preference": list(plan.device_preference),
                "native_hacf_built": plan.build_native_hacf,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
