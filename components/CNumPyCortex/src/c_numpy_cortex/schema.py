from __future__ import annotations

from pathlib import Path
from typing import Any
import tomllib

from .contracts import (
    ChannelDescriptor,
    ChannelSchema,
    MISSING_CHANNEL,
    compute_schema_digest,
)


def load_channel_schema(path: str | Path) -> ChannelSchema:
    """Load and validate a pinned channel schema from TOML."""
    schema_path = Path(path)

    if not schema_path.exists():
        raise FileNotFoundError(
            f"Channel schema not found: {schema_path}"
        )

    with schema_path.open("rb") as handle:
        data = tomllib.load(handle)

    metadata = data.get("metadata", {})
    schema_id = str(metadata.get("schema_id", "default"))
    version = str(metadata.get("version", "1.0"))

    raw_rows = data.get("channels", [])

    if len(raw_rows) != 9:
        raise ValueError(
            f"Channel schema must have exactly 9 rows, "
            f"got {len(raw_rows)}"
        )

    rows: list[ChannelDescriptor] = []

    for i, raw in enumerate(raw_rows):
        is_missing = raw.get("source_kind") == "missing"

        if is_missing:
            rows.append(
                MISSING_CHANNEL.with_missing_index(i)
                if hasattr(MISSING_CHANNEL, "with_missing_index")
                else MISSING_CHANNEL
            )
        else:
            rows.append(
                ChannelDescriptor(
                    channel_id=str(raw["channel_id"]),
                    source_kind=str(raw["source_kind"]),
                    unit=str(raw.get("unit", "none")),
                    sampling_class=str(raw["sampling_class"]),
                    expected_period_ns=int(raw["expected_period_ns"]),
                    stale_after_ns=int(raw["stale_after_ns"]),
                    transform_id=str(raw.get("transform_id", "robust_z")),
                    required=bool(raw.get("required", False)),
                )
            )

    digest = compute_schema_digest(tuple(rows))

    return ChannelSchema(
        schema_id=schema_id,
        version=version,
        rows=tuple(rows),
        digest=digest,
    )


def propose_channel_schema(
    live_channels: list[ChannelDescriptor],
    output_path: str | Path,
) -> ChannelSchema:
    """Create a 9-row schema from live channels, padding with MISSING."""
    rows: list[ChannelDescriptor] = list(live_channels)

    while len(rows) < 9:
        rows.append(MISSING_CHANNEL)

    rows = rows[:9]
    digest = compute_schema_digest(tuple(rows))

    schema = ChannelSchema(
        schema_id="proposed",
        version="1.0",
        rows=tuple(rows),
        digest=digest,
    )

    toml_lines = ["[metadata]\n", 'schema_id = "proposed"\n', 'version = "1.0"\n', "\n"]

    for i, row in enumerate(rows):
        toml_lines.append(f'[[channels]]\n')
        toml_lines.append(f'channel_id = "{row.channel_id}"\n')
        toml_lines.append(f'source_kind = "{row.source_kind}"\n')
        toml_lines.append(f'unit = "{row.unit}"\n')
        toml_lines.append(
            f'sampling_class = "{row.sampling_class}"\n'
        )
        toml_lines.append(
            f'expected_period_ns = {row.expected_period_ns}\n'
        )
        toml_lines.append(f'stale_after_ns = {row.stale_after_ns}\n')
        toml_lines.append(
            f'transform_id = "{row.transform_id}"\n'
        )
        toml_lines.append(f'required = {str(row.required).lower()}\n')
        toml_lines.append("\n")

    Path(output_path).write_text("".join(toml_lines))

    return schema
