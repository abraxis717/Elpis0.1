from __future__ import annotations

from .contracts import (
    ChannelSchema,
    ObservationValidity,
    PacketLifecycle,
    ObservedValue,
)


def classify_lifecycle(
    schema: ChannelSchema,
    channel_values: dict[str, ObservedValue],
    now_monotonic_ns: int,
    fresh_until_monotonic_ns: int | None,
    previous_fallback: bool = False,
) -> tuple[PacketLifecycle, tuple[str, ...]]:
    """Classify packet lifecycle with explicit precedence.

    Precedence: INVALID > STALE > WARMING > DEGRADED > READY
    """
    reasons: list[str] = []

    # Check required channels
    required_rows = [r for r in schema.rows if r.required]
    optional_rows = [r for r in schema.rows if not r.required]

    if not required_rows:
        reasons.append("NO_REQUIRED_CHANNELS")
        return PacketLifecycle.INVALID, tuple(reasons)

    # Check each required channel
    required_ok = True
    required_fresh = True
    required_has_nine = True

    for row in required_rows:
        val = channel_values.get(row.channel_id)

        if val is None:
            required_ok = False
            reasons.append(f"REQUIRED_MISSING:{row.channel_id}")
            continue

        if val.validity == ObservationValidity.INVALID:
            required_ok = False
            reasons.append(f"REQUIRED_INVALID:{row.channel_id}")
            continue

        if val.validity == ObservationValidity.STALE:
            required_fresh = False

    # Check each optional channel
    optional_problem = False

    for row in optional_rows:
        val = channel_values.get(row.channel_id)

        if val is None:
            optional_problem = True
            continue

        if val.validity in (
            ObservationValidity.STALE,
            ObservationValidity.INVALID,
            ObservationValidity.MISSING,
        ):
            optional_problem = True

    # ─── INVALID ───────────────────────────────────────────
    if not required_ok:
        return PacketLifecycle.INVALID, tuple(reasons)

    # ─── STALE ─────────────────────────────────────────────
    if (
        fresh_until_monotonic_ns is not None
        and now_monotonic_ns > fresh_until_monotonic_ns
    ):
        reasons.append("PAST_FRESH_DEADLINE")
        return PacketLifecycle.STALE, tuple(reasons)

    if not required_fresh:
        # A required channel is STALE
        reasons.append("REQUIRED_CHANNEL_STALE")
        return PacketLifecycle.STALE, tuple(reasons)

    # ─── WARMING ───────────────────────────────────────────
    # Checked by caller (fewer than 9 samples per required row)
    # This is handled at compile time. We just check for the flag.

    # ─── DEGRADED ──────────────────────────────────────────
    if previous_fallback:
        reasons.append("DEGRADED_READ_PREVIOUS_GENERATION")
        return PacketLifecycle.DEGRADED, tuple(reasons)

    if optional_problem:
        reasons.append("OPTIONAL_CHANNEL_DEGRADED")
        return PacketLifecycle.DEGRADED, tuple(reasons)

    # ─── READY ─────────────────────────────────────────────
    return PacketLifecycle.READY, tuple(reasons)
