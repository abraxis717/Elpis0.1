# elpis/contracts/identity.py — A1 identity law (§V).
# Three identities, never conflated:
#   chi_p  = H(domain=payload | type | schema | canon(payload))        content
#   chi_r  = H(domain=record  | chi_p | parents | authority | security | validity | observation)
#   iota   = fresh UUID, event identity; NEVER hashed into chi_p or chi_r.
# Participation table (T2):
#   record_id/claim_id/packet_id -> iota only.   timestamps -> chi_r only.
#   parents -> chi_r, SORTED (set semantics).    citations -> payload, ORDER KEPT.
#   route/budget/device/dtype -> neither chi (control/trajectory, not evidence).
# Fixes A0 defect: landed compute_record_checksum included record_id.
from __future__ import annotations

import dataclasses
import hashlib
import math
import uuid
from enum import Enum
from typing import Any, Mapping, Sequence

IDENTITY_SCHEMA = 2          # v1 = landed C0 (record_id leaked); v2 = this law.
_DOMAIN = b"ELPIS-ID\x00"


class CanonError(TypeError):
    pass


def _canon(v: Any) -> bytes:
    if v is None:
        return b"N;"
    if isinstance(v, bool):
        return b"B1;" if v else b"B0;"
    if isinstance(v, Enum):  # BEFORE str/int: str-Enums must never coalesce
        tag = f"{type(v).__module__}.{type(v).__qualname__}"
        raw = v.value
        if isinstance(raw, Enum):          # nested enums: canonicalize by str
            raw = str(raw)
        return b"E" + _canon(tag) + _canon(raw)
    if isinstance(v, int):
        return b"I" + str(v).encode() + b";"
    if isinstance(v, float):
        if not math.isfinite(v):
            raise CanonError("non-finite float is not canonical")
        return b"F" + repr(v).encode() + b";"
    if isinstance(v, str):
        b = v.encode("utf-8")
        return b"S" + str(len(b)).encode() + b":" + b
    if isinstance(v, (bytes, bytearray)):
        return b"Y" + str(len(v)).encode() + b":" + bytes(v)
    if isinstance(v, (list, tuple)):  # sequences coalesce by design (ordered)
        return b"L[" + b"".join(_canon(x) for x in v) + b"]"
    if isinstance(v, (set, frozenset)):
        raise CanonError("sets are not canonical; sort into a tuple explicitly")
    if isinstance(v, Mapping):
        if not all(isinstance(k, str) for k in v):
            raise CanonError("mapping keys must be str")
        items = sorted(v.items())
        return b"D{" + b"".join(_canon(k) + _canon(x) for k, x in items) + b"}"
    if dataclasses.is_dataclass(v) and not isinstance(v, type):
        tag = getattr(v, "TYPE_TAG", type(v).__qualname__)
        d = {f.name: getattr(v, f.name) for f in dataclasses.fields(v)}
        return b"C" + _canon(tag) + _canon(d)
    raise CanonError(f"non-canonical type: {type(v)!r}")


def _h(*parts: bytes) -> str:
    h = hashlib.blake2b(digest_size=12)  # 96-bit, intentional (F0 §5.4)
    h.update(_DOMAIN)
    for p in parts:
        h.update(p)
        h.update(b"\x00")
    return h.hexdigest()


def chi_payload(type_tag: str, payload: Mapping[str, Any] | bytes,
                schema_version: int = IDENTITY_SCHEMA) -> str:
    body = payload if isinstance(payload, bytes) else _canon(payload)
    return _h(b"payload", type_tag.encode(), str(schema_version).encode(), body)


def chi_record(chi_p: str, *, parents: Sequence[str], authority: Any,
               security: Any, valid_from: float | None,
               valid_until: float | None, observed_at: float | None) -> str:
    return _h(
        b"record", chi_p.encode(),
        _canon(tuple(sorted(parents))),          # set semantics for lineage
        _canon(authority), _canon(security),
        _canon(valid_from), _canon(valid_until), _canon(observed_at),
    )


def new_instance_id() -> str:
    return uuid.uuid4().hex[:16]


# Migration (no silent rewrite): stored v1 checksums keep their column
# (legacy_checksum). New writes compute v2. Lookup order: v2 then v1.
# A consolidation pass MAY add v2 alongside v1; it MUST NOT delete v1.
LOOKUP_ORDER = ("chi_v2", "chi_v1_legacy")
