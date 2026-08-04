import pytest

from elpis_nanbeige42_host.digest import validate_digest
from elpis_nanbeige42_host.errors import ActionSchemaViolation, ControlShapeMismatch
from elpis_nanbeige42_host.schemas import (
    ActionKind, CodingAction, CollapseControlPacket, CommandPayload,
    ExplainPayload, GenerationShape,
)

def packet():
    return CollapseControlPacket(
        schema="elpis.collapse-control.v1",
        common=0.25,
        structural=tuple(float(i) / 21 for i in range(21)),
        source_state_digest="sha256:source",
        gain=1.0,
    ).with_digest()

def test_packet_has_22_coordinates_and_no_authority_fields():
    p = packet()
    assert len(p.structural) == 21
    assert validate_digest(p, digest_field="packet_digest")
    assert not hasattr(p, "authority")
    assert not hasattr(p, "polarity")
    assert not hasattr(p, "confidence")

def test_packet_rejects_shape_drift():
    with pytest.raises(ControlShapeMismatch):
        CollapseControlPacket(
            schema="elpis.collapse-control.v1", common=0.0,
            structural=(0.0,) * 20, source_state_digest="sha256:x", gain=1.0,
        )

def test_generation_shape_is_two_loop():
    assert GenerationShape(2, 17, 3).forward_passes == 4

def test_action_payload_is_typed():
    with pytest.raises(ActionSchemaViolation):
        CodingAction(
            schema="elpis.nanbeige42.coding-action.v1", action_id="a", tick_id="t",
            kind=ActionKind.RUN_COMMAND, payload=ExplainPayload("bad"),
            rationale_summary="", expected_result="",
        )
    action = CodingAction(
        schema="elpis.nanbeige42.coding-action.v1", action_id="a", tick_id="t",
        kind=ActionKind.RUN_COMMAND, payload=CommandPayload("pytest_focused"),
        rationale_summary="run focused tests", expected_result="zero exit",
    ).with_digest()
    assert validate_digest(action, digest_field="action_digest")
