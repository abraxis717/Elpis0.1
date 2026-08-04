import pytest

from elpis_nanbeige42_host.errors import HookInvocationDrift
from elpis_nanbeige42_host.hooks import InvocationEvent, default_registry
from elpis_nanbeige42_host.schemas import GenerationShape

def test_registry_has_loop_qualified_layer_anchors():
    registry = default_registry()
    layer_ids = [h.anchor_id for h in registry.hooks if "LAYER_" in h.anchor_id]
    assert layer_ids
    assert all("_L1_" in anchor for anchor in layer_ids)

def test_invocation_predicate_uses_generation_shape():
    shape = GenerationShape(num_loops=2, prefill_tokens=12, decode_steps=2)
    rule = next(h.invocation_rule for h in default_registry().hooks if h.anchor_id == "LAYER_10_L1_POST")
    events = (
        InvocationEvent(0, 1, None, 12, "prefill"),
        InvocationEvent(1, 1, None, 1, "decode"),
        InvocationEvent(2, 1, None, 1, "decode"),
    )
    rule.validate(events, shape)
    with pytest.raises(HookInvocationDrift):
        rule.validate(events[:-1], shape)


def test_norm_anchors_are_disambiguated_by_module_call_ordinal():
    registry = default_registry()
    by_id = {hook.anchor_id: hook for hook in registry.hooks}
    assert by_id["INTER_LOOP_SEAM_POST"].invocation_rule.module_call_ordinal == 0
    assert by_id["FINAL_NORM_POST"].invocation_rule.module_call_ordinal == 1
    shape = GenerationShape(num_loops=2, prefill_tokens=9, decode_steps=1)
    seam_events = (
        InvocationEvent(0, None, 0, 9, "prefill"),
        InvocationEvent(1, None, 0, 1, "decode"),
    )
    by_id["INTER_LOOP_SEAM_POST"].invocation_rule.validate(seam_events, shape)
    with pytest.raises(HookInvocationDrift):
        by_id["FINAL_NORM_POST"].invocation_rule.validate(seam_events, shape)
