import pickle
import pytest

from elpis_nanbeige42_host.capabilities import ActuationCapabilityIssuer
from elpis_nanbeige42_host.errors import ActuationCapabilityConsumed, ActuationCapabilityScopeMismatch
from elpis_nanbeige42_host.schemas import ControlMode

def test_capability_is_use_once_and_nonserializable():
    cap = ActuationCapabilityIssuer().issue(
        tick_id="tick-1", mode=ControlMode.DOCK,
        not_before=7, not_after=7, max_gain=1.0,
    )
    with pytest.raises(TypeError):
        pickle.dumps(cap)
    receipt = cap.consume(
        tick_id="tick-1", mode=ControlMode.DOCK, logical_time=7,
        packet_digest="sha256:packet", gain=1.0,
    )
    assert receipt.receipt_digest.startswith("sha256:")
    with pytest.raises(ActuationCapabilityConsumed):
        cap.consume(
            tick_id="tick-1", mode=ControlMode.DOCK, logical_time=7,
            packet_digest="sha256:packet", gain=1.0,
        )

def test_packet_gain_does_not_grant_authority():
    issuer = ActuationCapabilityIssuer()
    with pytest.raises(ActuationCapabilityScopeMismatch):
        issuer.issue(
            tick_id="tick-1", mode=ControlMode.OBSERVE,
            not_before=1, not_after=1, max_gain=1.0,
        )
