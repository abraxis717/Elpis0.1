from __future__ import annotations

from datetime import datetime, timezone


def format_diagnostic_line(
    *,
    generation: int,
    monotonic_ns: int,
    wall_time_ns: int,
    component: str,
    event: str,
    status: str,
    source_sequence: int | None = None,
    extra: dict | None = None,
) -> str:
    """Produce a single canonical diagnostic line."""
    dt = datetime.fromtimestamp(
        wall_time_ns / 1e9,
        tz=timezone.utc,
    )
    wall_iso = dt.isoformat(timespec="milliseconds")

    parts = [
        f"wall_time_iso_ms={wall_iso}",
        f"generation={generation}",
        f"monotonic_ns={monotonic_ns}",
    ]

    if source_sequence is not None:
        parts.append(f"source_sequence={source_sequence}")

    parts.append(f"component={component}")
    parts.append(f"event={event}")
    parts.append(f"status={status}")

    if extra:
        for k, v in extra.items():
            parts.append(f"{k}={v}")

    return " ".join(parts)
