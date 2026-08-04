from elpis_nanbeige42_host.digest import validate_digest
from elpis_nanbeige42_host.schemas import ControlMode, TickEvidence

def test_cache_fingerprints_are_part_of_evidence_digest():
    evidence = TickEvidence(
        schema="elpis.nanbeige42.tick-evidence.v1",
        tick_id="t", input_digest="sha256:i", model_manifest_digest="sha256:m",
        hook_registry_digest="sha256:h", executor_policy_digest="sha256:p",
        control_mode=ControlMode.OBSERVE, control_packet_digest=None,
        hook_trace_digest="sha256:trace", seam_pre_digest="sha256:a",
        seam_post_digest="sha256:b", checkpoint_digests={},
        kv_cache_fingerprint_before="sha256:k0",
        kv_cache_fingerprint_after="sha256:k1",
        raw_logits_digest="sha256:l", controlled_logits_digest=None,
        generated_action_digest=None, executor_receipt_digest=None,
        failure_code=None,
    ).with_digest()
    assert validate_digest(evidence, digest_field="evidence_digest")
    changed = TickEvidence(
        schema=evidence.schema, tick_id=evidence.tick_id,
        input_digest=evidence.input_digest,
        model_manifest_digest=evidence.model_manifest_digest,
        hook_registry_digest=evidence.hook_registry_digest,
        executor_policy_digest=evidence.executor_policy_digest,
        control_mode=evidence.control_mode,
        control_packet_digest=evidence.control_packet_digest,
        hook_trace_digest=evidence.hook_trace_digest,
        seam_pre_digest=evidence.seam_pre_digest,
        seam_post_digest=evidence.seam_post_digest,
        checkpoint_digests=evidence.checkpoint_digests,
        kv_cache_fingerprint_before="sha256:changed",
        kv_cache_fingerprint_after=evidence.kv_cache_fingerprint_after,
        raw_logits_digest=evidence.raw_logits_digest,
        controlled_logits_digest=evidence.controlled_logits_digest,
        generated_action_digest=evidence.generated_action_digest,
        executor_receipt_digest=evidence.executor_receipt_digest,
        failure_code=evidence.failure_code,
        evidence_digest=evidence.evidence_digest,
    )
    assert not validate_digest(changed, digest_field="evidence_digest")
