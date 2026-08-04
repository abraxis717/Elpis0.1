from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import tomllib


# ─── Sampling rates ─────────────────────────────────────────────────────

PSUTIL_RATE_HZ = 20.0
HWMON_RATE_HZ = 10.0
NVIDIA_RATE_HZ = 2.0
LLAMA_RATE_HZ = 1.0
CHRONOS_RATE_HZ = 0.2

# ─── Retention ──────────────────────────────────────────────────────────

RETENTION_COUNT = 4

# ─── Health endpoints ───────────────────────────────────────────────────

HEALTH_ENDPOINTS = [
    ("127.0.0.1", 8080),
    ("127.0.0.1", 8081),
]

# ─── Config dataclasses ─────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class LoopConfig:
    sample_hz: float = 20.0
    compile_hz: float = 10.0
    print_hz: float = 10.0
    forecast_interval_s: float = 5.0
    ring_capacity: int = 4096


@dataclass(frozen=True, slots=True)
class ChronosConfig:
    enabled: bool = True
    model_path: str = (
        "$ELPIS_CANON_ROOT/Elpis_Canon/Models/chronos-2"
    )
    device: str = "cpu"
    context_points: int = 256
    prediction_length: int = 8
    resample_rule: str = "200ms"
    min_points: int = 32


@dataclass(frozen=True, slots=True)
class SensorConfig:
    include_hwmon: bool = True
    include_cpu_threads: bool = True
    include_nvidia: bool = True
    llama_poll_interval_s: float = 1.0
    llama_timeout_s: float = 0.20


@dataclass(frozen=True, slots=True)
class CompilerConfig:
    channels: tuple[str, ...] = ()
    normalization_window: int = 256
    clip_z: float = 3.0


@dataclass(frozen=True, slots=True)
class OutputConfig:
    grid_npz: str = (
        "$ELPIS_CANON_ROOT/Elpis_Canon/"
        "CNumPyCortex/runtime/grid81_latest.npz"
    )
    state_json: str = (
        "$ELPIS_CANON_ROOT/Elpis_Canon/"
        "CNumPyCortex/runtime/state_latest.json"
    )


@dataclass(frozen=True, slots=True)
class LlamaEndpoint:
    name: str
    url: str


@dataclass(frozen=True, slots=True)
class CortexConfig:
    loop: LoopConfig = field(default_factory=LoopConfig)
    chronos: ChronosConfig = field(default_factory=ChronosConfig)
    sensors: SensorConfig = field(default_factory=SensorConfig)
    compiler: CompilerConfig = field(
        default_factory=CompilerConfig
    )
    output: OutputConfig = field(default_factory=OutputConfig)
    llama_endpoints: tuple[LlamaEndpoint, ...] = ()
    retention_count: int = RETENTION_COUNT
    channel_schema_path: str = "config/channel_schema.toml"


def _section(
    data: dict[str, Any],
    name: str,
) -> dict[str, Any]:
    value = data.get(name, {})

    if not isinstance(value, dict):
        raise TypeError(f"[{name}] must be a TOML table")

    return value


def load_config(path: str | Path) -> CortexConfig:
    with Path(path).open("rb") as handle:
        data = tomllib.load(handle)

    compiler_data = _section(data, "compiler")
    compiler_data["channels"] = tuple(
        compiler_data.get("channels", ())
    )

    llama_data = _section(data, "llama")
    raw_endpoints = llama_data.get("endpoints", ())

    endpoints = tuple(
        LlamaEndpoint(
            name=str(item["name"]),
            url=str(item["url"]).rstrip("/"),
        )
        for item in raw_endpoints
    )

    loop_data = _section(data, "loop")
    chronos_data = _section(data, "chronos")
    sensors_data = _section(data, "sensors")
    output_data = _section(data, "output")

    retention = data.get("retention", {})
    retention_count = retention.get("generations", RETENTION_COUNT)

    schema_path = data.get(
        "channel_schema_path",
        "config/channel_schema.toml",
    )

    return CortexConfig(
        loop=LoopConfig(**loop_data),
        chronos=ChronosConfig(**chronos_data),
        sensors=SensorConfig(**sensors_data),
        compiler=CompilerConfig(**compiler_data),
        output=OutputConfig(**output_data),
        llama_endpoints=endpoints,
        retention_count=retention_count,
        channel_schema_path=schema_path,
    )
