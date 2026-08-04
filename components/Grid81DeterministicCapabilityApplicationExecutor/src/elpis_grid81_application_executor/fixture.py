"""G5.3C Shadow fixture generation.

Creates deterministic shadow fixtures derived from G5.3B accepted artifacts.
Fixtures are isolated — they do not reference or mutate canonical state.
"""
from .canonical import canonical_digest
from .shadow_state import ShadowCapabilityState


class MutableShadowState:
    """Mutable wrapper around ShadowCapabilityState for replay testing.

    The real apply_artifact() uses optimistic digest comparison and constructs
    new states in memory. This wrapper lets mutation tests simulate state
    transitions for replay verification.
    """

    def __init__(self, state: ShadowCapabilityState):
        self._state = state

    @property
    def state(self) -> ShadowCapabilityState:
        return self._state

    @state.setter
    def state(self, new_state: ShadowCapabilityState):
        self._state = new_state

    def transition_to_applied(self, artifact_digest: str) -> ShadowCapabilityState:
        """Transition shadow state to APPLIED. Returns new state."""
        self._state = ShadowCapabilityState(
            capability_digest=self._state.capability_digest,
            application_state="APPLIED",
            consumption_count=self._state.consumption_count + 1,
            current_lifecycle_state=self._state.current_lifecycle_state,
            applied_artifact_digest=artifact_digest,
        )
        return self._state


def create_shadow_fixture(index: int, scope_size: int = 1) -> dict:
    """Create a deterministic shadow fixture capability record."""
    proposals = [canonical_digest({"proposal": i, "fixture": index})
                 for i in range(scope_size)]
    cap = {
        "schema_version": "structural-influence-capability.v1",
        "capability_class": "STRUCTURAL_INFLUENCE_CAPABILITY_V1",
        "capability_digest": canonical_digest({"cap": index, "fixture_domain": True}),
        "capability_semantic_digest": canonical_digest({"sem": index, "fixture_domain": True}),
        "nonce_digest": canonical_digest({"nonce": index, "fixture_domain": True}),
        "authorized_proposal_digests": proposals,
        "authorized_consumer_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "authorized_operation_class": "PRODUCE_BOUNDED_STRUCTURAL_INFLUENCE_V1",
        "source_request_digest": canonical_digest({"req": index, "fixture_domain": True}),
        "source_adjudication_record_digest": canonical_digest({"adj": index, "fixture_domain": True}),
        "source_proposal_set_digest": canonical_digest({"set": index, "fixture_domain": True}),
        "fixture_domain": True,
        "source_capability_digest": canonical_digest({"src": index}),
        "current_lifecycle_state": "CONSUMED",
        "consumption_count": 1,
    }
    return cap


def create_shadow_artifact(fixture: dict, index: int) -> dict:
    """Create a deterministic shadow artifact for a fixture capability."""
    proposals = fixture["authorized_proposal_digests"]
    bindings = []
    for p in proposals:
        bindings.append({
            "proposal_digest": p,
            "binding_class": "STRUCTURAL_PROPOSAL_BINDING_V1",
        })

    # Build artifact payload (without digest)
    compiler_contract_digest = canonical_digest({"compiler_contract": "v1", "fixture": True})
    artifact_payload = {
        "schema_version": "structural-influence-artifact.v1",
        "artifact_class": "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1",
        "materialization_class": "MATERIALIZE_AUTHORIZED_STRUCTURAL_INFLUENCE_SET_V1",
        "application_state": "UNAPPLIED",
        "consumer_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "authorized_consumer_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "authorized_proposal_digests": proposals,
        "proposal_bindings": bindings,
        "source_capability_digest": fixture["capability_digest"],
        "source_capability_semantic_digest": fixture["capability_semantic_digest"],
        "structural_influence_scope_digest": canonical_digest({"scope": proposals, "fixture": index}),
        "consumption_request_digest": canonical_digest({"req": index, "artifact": True}),
        "compiler_contract_digest": compiler_contract_digest,
        "max_consumptions": 1,
        "target_domain_class": "GRID81_STRUCTURAL_PROPOSAL_DOMAIN_V1",
    }

    # Compute artifact digest
    artifact_digest = canonical_digest(artifact_payload)
    artifact_payload["artifact_digest"] = artifact_digest
    artifact_payload["artifact_semantic_digest"] = canonical_digest({
        "artifact_class": artifact_payload["artifact_class"],
        "authorized_proposal_digests": proposals,
        "consumer_class": artifact_payload["consumer_class"],
        "materialization_class": artifact_payload["materialization_class"],
    })

    return artifact_payload


def mutate_and_rehash(base_artifact: dict, field: str, new_value) -> dict:
    """Mutate a field in the artifact and recompute the digest.

    This allows testing guards AFTER the digest check (guard 3), since
    the digest is recomputed to match the mutated content.
    """
    import copy
    mutated = copy.deepcopy(base_artifact)
    # Apply mutation
    if isinstance(field, list):
        for f in field:
            mutated[f] = new_value
    else:
        mutated[field] = new_value
    # Recompute digest to pass guard 3
    digest_payload = {k: v for k, v in mutated.items()
                      if k not in ("artifact_digest", "artifact_semantic_digest")}
    mutated["artifact_digest"] = canonical_digest(digest_payload)
    return mutated


def create_mutation_artifact(base_artifact: dict, mutation: dict) -> dict:
    """Apply a mutation to an artifact for adversarial testing.

    For mutations that should trigger guards AFTER digest check,
    the digest is recomputed. For digest-specific mutations, it is NOT.
    """
    import copy
    mutated = copy.deepcopy(base_artifact)

    mutation_type = mutation.get("type", "")

    if mutation_type == "invalid_schema":
        # Don't rehash — we want schema to fail (guard 1, before digest)
        mutated["schema_version"] = "invalid-schema.v99"
    elif mutation_type == "applied_state":
        # Recompute digest so guard 2 catches it, not guard 3
        mutated = mutate_and_rehash(base_artifact, "application_state", "APPLIED")
    elif mutation_type == "digest_mismatch":
        # Don't rehash — we want digest check (guard 3) to catch this
        mutated["artifact_digest"] = "0" * 64
    elif mutation_type == "compiler_mismatch":
        mutated = mutate_and_rehash(base_artifact, "compiler_contract_digest",
                                     canonical_digest({"wrong_compiler": True}))
    elif mutation_type == "capability_mismatch":
        mutated = mutate_and_rehash(base_artifact, "source_capability_digest",
                                     canonical_digest({"wrong_cap": True}))
    elif mutation_type == "consumer_mismatch":
        mutated = mutate_and_rehash(base_artifact, "consumer_class", "UNAUTHORIZED_CONSUMER")
    elif mutation_type == "forbidden_field":
        mutated = mutate_and_rehash(base_artifact, "winner", "should_not_be_here")
    elif mutation_type == "scope_mismatch":
        # Recompute digest after removing a binding
        import copy
        mutated = copy.deepcopy(base_artifact)
        mutated["proposal_bindings"] = mutated["proposal_bindings"][:max(0, len(mutated["proposal_bindings"]) - 1)]
        digest_payload = {k: v for k, v in mutated.items()
                          if k not in ("artifact_digest", "artifact_semantic_digest")}
        mutated["artifact_digest"] = canonical_digest(digest_payload)
    elif mutation_type == "purpose_mismatch":
        mutated = mutate_and_rehash(base_artifact, "materialization_class",
                                     "INVALID_MATERIALIZATION")
    elif mutation_type == "invalid_hex":
        # Don't rehash — we want hex check (guard 3) to catch this
        mutated["artifact_digest"] = "g" * 64
    elif mutation_type == "canonical_write":
        mutated = mutate_and_rehash(base_artifact, "canonical_path", "/should/not/exist")
    elif mutation_type == "malformed_nested":
        # Recompute digest so guard catches the structural issue, not digest
        mutated["proposal_bindings"] = [None]
        digest_payload = {k: v for k, v in mutated.items()
                          if k not in ("artifact_digest", "artifact_semantic_digest")}
        mutated["artifact_digest"] = canonical_digest(digest_payload)
    elif mutation_type == "empty_bindings":
        mutated = mutate_and_rehash(base_artifact, "proposal_bindings", [])
    elif mutation_type == "injected_forbidden":
        mutated = mutate_and_rehash(base_artifact, "model_id", "injected_model")
    elif mutation_type == "noncanonical_order":
        pass  # canonical_json handles ordering

    return mutated
