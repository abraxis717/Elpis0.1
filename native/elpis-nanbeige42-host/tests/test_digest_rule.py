from dataclasses import dataclass
import math
import pytest

from elpis_nanbeige42_host.digest import canonical_bytes, canonical_digest, validate_digest
from elpis_nanbeige42_host.errors import DigestRuleViolation

@dataclass(frozen=True)
class Obj:
    x: float
    nested_digest: str
    object_digest: str = ""

def test_digest_excludes_only_named_top_level_field():
    first = Obj(1.25, "sha256:nested", "")
    digest = canonical_digest(first, digest_field="object_digest")
    second = Obj(1.25, "sha256:nested", digest)
    assert validate_digest(second, digest_field="object_digest")
    assert b"nested_digest" in canonical_bytes(second, digest_field="object_digest")

def test_float_is_exact_hex_tag():
    payload = canonical_bytes({"x": 0.1})
    assert b"$elpis_f64_hex" in payload
    assert b"0x1.999999999999ap-4" in payload

def test_nonfinite_float_rejected():
    with pytest.raises(DigestRuleViolation):
        canonical_digest({"x": math.nan})
