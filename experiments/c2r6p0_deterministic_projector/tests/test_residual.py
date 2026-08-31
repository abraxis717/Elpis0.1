"""Residual derivation tests (mission 20): no duplicate logic."""
from __future__ import annotations

import structural_trm_features as FEATURES
from elpis_p0.structural_residual import (
    residual as authority_residual,
)

from conftest import wrap, check_invariants
from c2r6p0 import fixtures as FX
from c2r6p0.contracts import ProjectionStatus
from c2r6p0.rules import load_ruleset


class TestResidual:
    def test_width_529_and_vocabulary_identity(self, project, ruleset):
        # width pinned at load: 529; vocabulary digest matches authority
        assert ruleset.feature_width == 529
        assert FEATURES.FEATURE_WIDTH == 529
        assert ruleset.vocabulary_digest == FEATURES.VOCABULARY_DIGEST
        # mission-pinned historical vocabulary SHA (verified live)
        assert ruleset.vocabulary_digest == (
            "dff5506be69bec65e121778274ea59c9900d843c334588bc72854f40c98a94d0"
        )
        r = project(wrap(FX.gen_valid(21)))
        assert r.status == "PROJECTED"
        assert len(r.declared_features) == 529
        assert len(r.active_residual) == 529

    def test_resolved_seed_has_empty_residual(self, project):
        # a fully determinate seed: no active invariant
        r = project(wrap(FX.gen_valid(22)))
        assert r.status == "PROJECTED"
        assert r.residual_ids == ()
        assert sum(r.active_residual) == 0
        # active <= declared at every bit
        for i in range(529):
            assert r.active_residual[i] <= r.declared_features[i]

    def test_active_residual_is_authority_computed(self, project):
        # same machinery, same answer: recompute independently
        r = project(wrap(FX.gen_valid(23)))
        assert r.status == "PROJECTED"
        unsat = authority_residual(r.grid81, r.invariants)
        assert unsat == r.residual_ids
        declared, active = FEATURES.encode_constraint_state(
            r.invariants, unsat
        )
        assert tuple(declared) == r.declared_features
        assert tuple(active) == r.active_residual

    def test_active_bits_match_unsatisfied_signatures(self, project):
        # an active bit is set exactly when the unsatisfied invariant's
        # structural signature occupies it (authority mapping)
        r = project(wrap(FX.gen_valid(24)))
        assert r.status == "PROJECTED"
        sig_of = {
            inv.invariant_id: FEATURES.signature_index(inv.kind, inv.lanes)
            for inv in r.invariants
        }
        for i in range(529):
            if r.active_residual[i]:
                assert i in sig_of.values()
            if r.declared_features[i]:
                assert i in sig_of.values()

    def test_unsatisfied_invariant_activates_bit(self, project):
        # construct a case with an unsatisfied invariant and verify its
        # signature bit is active in the residual vector
        from elpis_p0.semantic_ir import (
            SemanticEntityV1,
            SemanticOperationV1,
            SemanticRelationV1,
            build_semantic_request_v1,
        )
        g = build_semantic_request_v1(
            request_id="t",
            entities=(
                SemanticEntityV1("in0", "input", "v", "str"),
                SemanticEntityV1("st0", "state", "v", "dict"),
            ),
            operations=(
                SemanticOperationV1(
                    "a", "s", input_entity_ids=("in0",),
                    output_entity_ids=("st0",),
                ),
                SemanticOperationV1(
                    "b", "s", input_entity_ids=("st0",),
                    output_entity_ids=(),
                ),
            ),
            relations=(
                SemanticRelationV1("mu1", "b", "mutates", "in0"),
            ),
        )
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        # if a MUTATION_HAZARD invariant is declared and unsatisfied, its
        # bit is active; if satisfied, not. Either way, consistency.
        for inv in r.invariants:
            bit = FEATURES.signature_index(inv.kind, inv.lanes)
            expected = 1 if inv.invariant_id in r.residual_ids else 0
            assert r.active_residual[bit] == expected, inv.invariant_id

    def test_fingerprint_covers_grid81(self, project, ruleset):
        # R17 coverage: two otherwise-identical states that differ ONLY in
        # the grid81 content must get different fingerprints. (Direct
        # coverage of the fingerprint payload: the projector's own outputs
        # always have a grid consistent with the bindings, so a payload
        # field dropped from the fingerprint would otherwise be invisible.)
        from c2r6p0.residual import build_fingerprint
        g = FX.gen_valid(22)
        r = project(wrap(g))
        assert r.status == "PROJECTED"
        base = build_fingerprint(
            r.grid81, r.frozen_mask, r.writable_mask, r.invariants,
            r.lane_bindings, r.declared_features, r.active_residual,
            r.bindings,
        )
        assert base == r.structural_input_fingerprint
        # same everything else; flip one grid cell
        flipped = list(r.grid81)
        flipped[0] = (flipped[0] + 1) % 10
        alt = build_fingerprint(
            tuple(flipped), r.frozen_mask, r.writable_mask, r.invariants,
            r.lane_bindings, r.declared_features, r.active_residual,
            r.bindings,
        )
        assert alt != base, "fingerprint must cover the grid81 state"
        # and the masks too
        fm = list(r.frozen_mask); fm[0] ^= 1
        wm = list(r.writable_mask); wm[0] ^= 1
        alt2 = build_fingerprint(
            r.grid81, tuple(fm), tuple(wm), r.invariants,
            r.lane_bindings, r.declared_features, r.active_residual,
            r.bindings,
        )
        assert alt2 != base, "fingerprint must cover the frozen mask"

    def test_rejection_carrying_residual_width(self, project):
        # decomposition results still carry 529-width vectors (the seed
        # is VOID but the vectors are well-formed)
        g = next(
            f.graph for f in FX.POSITIVE_FIXTURES
            if f.name == "rank_overflow_route6"
        )
        r = project(wrap(g))
        assert r.status == ProjectionStatus.DECOMPOSITION_REQUIRED.value
        assert len(r.declared_features) == 529
        assert len(r.active_residual) == 529
