from __future__ import annotations

import argparse

from .config import load_config
from .runtime import build_runtime


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run C.NumPyCortex telemetry compiler"
    )

    parser.add_argument(
        "--config",
        default="config/cortex.toml",
        help="Path to cortex.toml",
    )

    arguments = parser.parse_args()
    config = load_config(arguments.config)

    world, scheduler, runtime_state = build_runtime(config)

    try:
        scheduler.run_forever(world)

    except KeyboardInterrupt:
        print("\nC.NumPyCortex stopped.")
        runtime_state.hub.stop_workers()

        if runtime_state.chronos_worker:
            runtime_state.chronos_worker.stop()


if __name__ == "__main__":
    main()
