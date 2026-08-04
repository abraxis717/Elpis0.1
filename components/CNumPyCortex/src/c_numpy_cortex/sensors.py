from __future__ import annotations

from pathlib import Path
import re
import subprocess
import threading
import time
from typing import Iterable

import psutil
import requests

from .airgap import (
    check_subprocess_allowed,
    instrument_airgap,
    uninstrument_airgap,
)
from .cache import WorkerCache
from .config import LlamaEndpoint, SensorConfig
from .contracts import (
    ObservedValue,
    ObservationValidity,
    TelemetrySample,
)
from .workers import Worker


_SAFE = re.compile(r"[^a-zA-Z0-9_.-]+")


def _key(text: str) -> str:
    return (
        _SAFE
        .sub("_", text.strip())
        .strip("_")
        .lower()
        or "unknown"
    )


class HwmonWorker(Worker):
    """hwmon cache worker — reads sysfs temperature sensors."""

    def __init__(
        self,
        cache: WorkerCache,
        interval_ns: int,
    ):
        super().__init__("hwmon_worker", interval_ns, cache)
        self._seq = 0

    def _tick(self) -> None:
        results: dict[str, ObservedValue] = {}

        try:
            paths = sorted(
                Path("/sys/class/hwmon").glob("hwmon*/temp*_input")
            )

            for input_path in paths:
                try:
                    chip_dir = input_path.parent
                    chip_name_path = chip_dir / "name"

                    chip = (
                        chip_name_path.read_text().strip()
                        if chip_name_path.exists()
                        else chip_dir.name
                    )

                    stem = input_path.name.removesuffix("_input")
                    label_path = chip_dir / f"{stem}_label"

                    label = (
                        label_path.read_text().strip()
                        if label_path.exists()
                        else stem
                    )

                    value_c = float(
                        input_path.read_text().strip()
                    ) / 1000.0

                    ch_id = f"temp.{_key(chip)}.{_key(label)}"
                    self._seq += 1

                    results[ch_id] = ObservedValue(
                        value=value_c,
                        observed_monotonic_ns=time.monotonic_ns(),
                        source_sequence=self._seq,
                        validity=ObservationValidity.FRESH,
                        error_code=None,
                    )

                except (OSError, ValueError):
                    continue

        except (OSError, ValueError):
            pass

        if results:
            self.cache.publish(results)


class NvidiaWorker(Worker):
    """NVIDIA GPU cache worker — reads nvidia-smi in subprocess."""

    def __init__(
        self,
        cache: WorkerCache,
        interval_ns: int,
    ):
        super().__init__("nvidia_worker", interval_ns, cache)
        self._seq = 0

    def _tick(self) -> None:
        results: dict[str, ObservedValue] = {}

        query = (
            "index,temperature.gpu,utilization.gpu,"
            "utilization.memory,power.draw,memory.used"
        )

        command = [
            "nvidia-smi",
            f"--query-gpu={query}",
            "--format=csv,noheader,nounits",
        ]

        if not check_subprocess_allowed(command):
            return

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=0.35,
                check=True,
                shell=False,
            )

            for line in completed.stdout.splitlines():
                fields = [
                    f.strip() for f in line.split(",")
                ]

                if len(fields) != 6:
                    continue

                try:
                    gpu_pci = fields[0]
                except ValueError:
                    continue

                names = (
                    "temp_c",
                    "util_pct",
                    "mem_util_pct",
                    "power_w",
                    "mem_used_mib",
                )

                for name, raw in zip(names, fields[1:]):
                    try:
                        val = float(raw)
                        ch_id = f"gpu.{gpu_pci}.{name}"
                        self._seq += 1

                        results[ch_id] = ObservedValue(
                            value=val,
                            observed_monotonic_ns=time.monotonic_ns(),
                            source_sequence=self._seq,
                            validity=ObservationValidity.FRESH,
                            error_code=None,
                        )
                    except ValueError:
                        continue

        except (OSError, subprocess.SubprocessError, ValueError):
            pass

        if results:
            self.cache.publish(results)


class LlamaHealthWorker(Worker):
    """Llama health poll worker — HTTP GET to loopback endpoints only."""

    def __init__(
        self,
        cache: WorkerCache,
        interval_ns: int,
        endpoints: tuple[LlamaEndpoint, ...],
        timeout_s: float = 0.20,
    ):
        super().__init__(
            "llama_health_worker", interval_ns, cache
        )
        self.endpoints = endpoints
        self.timeout_s = timeout_s
        self._session = requests.Session()
        self._seq = 0

    def _tick(self) -> None:
        results: dict[str, ObservedValue] = {}

        for endpoint in self.endpoints:
            started = time.perf_counter_ns()
            healthy = 0.0

            try:
                response = self._session.get(
                    f"{endpoint.url}/health",
                    timeout=self.timeout_s,
                )
                healthy = 1.0 if response.ok else 0.0

            except requests.RequestException:
                healthy = 0.0

            latency_ms = (
                time.perf_counter_ns() - started
            ) / 1_000_000.0

            prefix = f"llama.{_key(endpoint.name)}"
            self._seq += 1

            results[f"{prefix}.healthy"] = ObservedValue(
                value=healthy,
                observed_monotonic_ns=time.monotonic_ns(),
                source_sequence=self._seq,
                validity=ObservationValidity.FRESH,
                error_code=None,
            )

            self._seq += 1
            results[f"{prefix}.latency_ms"] = ObservedValue(
                value=latency_ms,
                observed_monotonic_ns=time.monotonic_ns(),
                source_sequence=self._seq,
                validity=ObservationValidity.FRESH,
                error_code=None,
            )

        if results:
            self.cache.publish(results)


# ─── Fast path psutil acquisition ───────────────────────────────────────

class PsutilFastReader:
    """Synchronous psutil reads for the fast 20 Hz path."""

    def __init__(self):
        self._seq = 0
        psutil.cpu_percent(interval=None, percpu=True)

    def read(self) -> dict[str, ObservedValue]:
        self._seq += 1
        now = time.monotonic_ns()

        per_cpu = psutil.cpu_percent(interval=None, percpu=True)
        cpu_total = float(sum(per_cpu) / max(len(per_cpu), 1))

        results: dict[str, ObservedValue] = {
            "cpu.total_pct": ObservedValue(
                value=cpu_total,
                observed_monotonic_ns=now,
                source_sequence=self._seq,
                validity=ObservationValidity.FRESH,
                error_code=None,
            ),
        }

        self._seq += 1
        results["memory.used_pct"] = ObservedValue(
            value=float(psutil.virtual_memory().percent),
            observed_monotonic_ns=now,
            source_sequence=self._seq,
            validity=ObservationValidity.FRESH,
            error_code=None,
        )

        return results


class SensorHub:
    """Multi-rate sensor acquisition with worker management."""

    def __init__(
        self,
        config: SensorConfig,
        llama_endpoints: Iterable[LlamaEndpoint] = (),
        hwmon_cache: WorkerCache | None = None,
        nvidia_cache: WorkerCache | None = None,
        llama_cache: WorkerCache | None = None,
    ):
        self.config = config
        self.llama_endpoints = tuple(llama_endpoints)
        self.fast_reader = PsutilFastReader()

        self.hwmon_cache = hwmon_cache or WorkerCache()
        self.nvidia_cache = nvidia_cache or WorkerCache()
        self.llama_cache = llama_cache or WorkerCache()

        self._hwmon_worker: HwmonWorker | None = None
        self._nvidia_worker: NvidiaWorker | None = None
        self._llama_worker: LlamaHealthWorker | None = None

        if config.include_hwmon:
            self._hwmon_worker = HwmonWorker(
                self.hwmon_cache,
                int(1e9 / 10),
            )

        if config.include_nvidia:
            self._nvidia_worker = NvidiaWorker(
                self.nvidia_cache,
                int(1e9 / 2),
            )

        if self.llama_endpoints:
            self._llama_worker = LlamaHealthWorker(
                self.llama_cache,
                int(1e9 / 1),
                self.llama_endpoints,
                config.llama_timeout_s,
            )

    def start_workers(self) -> None:
        if self._hwmon_worker:
            self._hwmon_worker.start()

        if self._nvidia_worker:
            self._nvidia_worker.start()

        if self._llama_worker:
            self._llama_worker.start()

    def stop_workers(self, timeout: float = 2.0) -> None:
        if self._hwmon_worker:
            self._hwmon_worker.stop(timeout)

        if self._nvidia_worker:
            self._nvidia_worker.stop(timeout)

        if self._llama_worker:
            self._llama_worker.stop(timeout)

    def fast_acquire(self) -> TelemetrySample:
        wall_ns = time.time_ns()
        mono_ns = time.monotonic_ns()

        values: dict[str, float] = {}
        fast = self.fast_reader.read()

        for ch_id, obs in fast.items():
            if obs.value is not None:
                values[ch_id] = obs.value

        # Read worker caches (fast path, no blocking)
        hwmon_data, _ = self.hwmon_cache.snapshot()
        for ch_id, obs in hwmon_data.items():
            if obs.value is not None:
                values[ch_id] = obs.value

        nvidia_data, _ = self.nvidia_cache.snapshot()
        for ch_id, obs in nvidia_data.items():
            if obs.value is not None:
                values[ch_id] = obs.value

        llama_data, _ = self.llama_cache.snapshot()
        for ch_id, obs in llama_data.items():
            if obs.value is not None:
                values[ch_id] = obs.value

        return TelemetrySample(
            wall_time_ns=wall_ns,
            monotonic_ns=mono_ns,
            values=values,
        )

    def discover_channels(
        self,
        samples: int = 3,
        delay_s: float = 0.05,
    ) -> tuple[str, ...]:
        names: set[str] = set()

        for _ in range(max(1, samples)):
            sample = self.fast_acquire()
            names.update(sample.values.keys())
            time.sleep(delay_s)

        return tuple(sorted(names))

    # Legacy compatibility
    def sample(self) -> TelemetrySample:
        return self.fast_acquire()
