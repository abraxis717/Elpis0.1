from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
import math
from typing import Any


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(
        value,
        (bool, int, str),
    ):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(
                "non-finite floats are not canonical"
            )

        return value

    if isinstance(value, enum.Enum):
        return value.value

    if dataclasses.is_dataclass(value) and not isinstance(
        value,
        type,
    ):
        return {
            field.name: to_jsonable(
                getattr(value, field.name)
            )
            for field in dataclasses.fields(value)
        }

    if isinstance(value, tuple):
        return [
            to_jsonable(item)
            for item in value
        ]

    if isinstance(value, list):
        return [
            to_jsonable(item)
            for item in value
        ]

    if isinstance(value, dict):
        if not all(
            isinstance(key, str)
            for key in value
        ):
            raise TypeError(
                "canonical dictionaries require string keys"
            )

        return {
            key: to_jsonable(value[key])
            for key in sorted(value)
        }

    raise TypeError(
        "unsupported canonical type: "
        f"{type(value).__qualname__}"
    )


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        to_jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def digest(
    value: Any,
    *,
    person: bytes = b"ELPIS-P0",
) -> str:
    return hashlib.blake2b(
        canonical_bytes(value),
        digest_size=32,
        person=person[:16],
    ).hexdigest()
