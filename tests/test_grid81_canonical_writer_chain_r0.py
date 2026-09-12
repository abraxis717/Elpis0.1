from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[1]
_REPO_ONLY_IMPORT_ROOTS = (
    REPO / "components",
    REPO / "components" / "Grid81DeterministicCanonicalPromotionAuthority" / "src",
    REPO / "components" / "Grid81DeterministicCanonicalCandidateConstructor" / "src",
    REPO / "components" / "Grid81DeterministicCanonicalPublisher" / "src",
)
for _root in reversed(_REPO_ONLY_IMPORT_ROOTS):
    _value = str(_root)
    if _value not in sys.path:
        sys.path.insert(0, _value)

import pytest

from Grid81.canonical_reader import load_current_grid81
from elpis_grid81_application_executor import DurableApplicationLedger
from elpis_grid81_candidate_constructor import construct_candidate
from elpis_grid81_consumption_compiler import canonical_digest
from elpis_grid81_promotion_authority import issue_promotion_capability
from elpis_grid81_promotion_planner.canonical import (
    CanonicalPromotionPlan,
    PhaseEvidence,
    PromotionDecision,
    SourceChain,
)
from elpis_grid81_promotion_planner.decision import DECISION_READY
from elpis_grid81_canonical_publisher import PublicationError, publish_candidate


SOURCE_GRID81 = (
    REPO / "components" / "Grid81" / "state" / "Canonical" / "Grid81"
)

INTENTIONS = (
    "VERIFY_CANONICAL_LEDGER_HEAD",
    "VERIFY_CAPABILITY_GRANTED_UNCONSUMED",
    "VERIFY_ARTIFACT_CANONICALLY_UNAPPLIED",
    "RESERVE_TRANSACTION_IDENTIFIER",
    "PERFORM_CANONICAL_APPLICATION",
    "APPEND_CANONICAL_RECEIPT",
    "VERIFY_POST_COMMIT_STATE",
)

PRECONDITIONS = (
    "canonical_ledger_head_verified",
    "capability_granted_and_unconsumed",
    "artifact_canonically_unapplied",
    "transaction_identifier_reserved",
    "post_commit_state_verified",
)


def _h(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_root(base: Path, name: str) -> Path:
    root = base / name
    (root / "Canonical").mkdir(parents=True)
    shutil.copytree(SOURCE_GRID81, root / "Canonical" / "Grid81")
    return root


def _tree_map(grid: Path) -> dict[str, str]:
    return {
        path.relative_to(grid).as_posix(): _sha(path)
        for path in sorted(grid.rglob("*"))
        if path.is_file()
    }


def _phase(
    phase_id: str,
    *,
    artifact_digest=None,
    capability_digest=None,
    lifecycle_state=None,
    receipt=None,
    state=None,
    ledger=None,
):
    return PhaseEvidence(
        phase_id=phase_id,
        source_directory=f"/evidence/{phase_id}",
        manifest_path=f"/evidence/{phase_id}/manifest.json",
        manifest_digest=_h(f"{phase_id}:manifest"),
        disposition="PASS",
        evidence_files=(("evidence.json", _h(f"{phase_id}:evidence"), 1),),
        artifact_digest=artifact_digest,
        capability_digest=capability_digest,
        lifecycle_state=lifecycle_state,
        shadow_receipt_digest=receipt,
        resulting_state_digest=state,
        resulting_ledger_head=ledger,
        bundle_digest=_h(f"{phase_id}:bundle"),
    )


def _artifact() -> dict:
    proposals = sorted({_h("proposal-A"), _h("proposal-B")})
    structural_capability = _h("structural-capability")

    bindings = []
    for proposal in proposals:
        binding_payload = {
            "proposal_digest": proposal,
            "source_capability_digest": structural_capability,
        }
        bindings.append({
            "schema_version": "structural-influence-proposal-binding.v1",
            "proposal_digest": proposal,
            "source_capability_digest": structural_capability,
            "binding_state": "INCLUDED_UNAPPLIED",
            "binding_digest": canonical_digest(binding_payload),
        })

    scope_digest = canonical_digest({
        "authorized_proposal_digests": proposals,
        "proposal_binding_digests": sorted(
            item["binding_digest"] for item in bindings
        ),
        "source_capability_digest": structural_capability,
    })

    artifact = {
        "schema_version": "structural-influence-artifact.v1",
        "artifact_class": "BOUNDED_STRUCTURAL_INFLUENCE_ARTIFACT_V1",
        "materialization_class": (
            "MATERIALIZE_AUTHORIZED_STRUCTURAL_INFLUENCE_SET_V1"
        ),
        "target_domain_class": "GRID81_STRUCTURAL_PROPOSAL_DOMAIN_V1",
        "source_capability_digest": structural_capability,
        "source_capability_semantic_digest": _h(
            "structural-capability-semantic"
        ),
        "source_request_digest": _h("source-request"),
        "source_adjudication_record_digest": _h("adjudication"),
        "source_proposal_set_digest": _h("proposal-set"),
        "authorized_proposal_digests": proposals,
        "proposal_bindings": bindings,
        "structural_influence_scope_digest": scope_digest,
        "consumer_class": "STRUCTURAL_INFLUENCE_COMPILER_V1",
        "consumer_contract_digest": _h("consumer-contract"),
        "consumption_request_digest": _h("consumption-request"),
        "consumption_receipt_digest": "",
        "logical_tick": 0,
        "application_state": "UNAPPLIED",
        "compiler_contract_digest": _h("compiler-contract"),
        "artifact_semantic_digest": "",
        "artifact_digest": "",
        "claims_not_made": sorted([
            "artifact does not activate runtime components",
            "artifact does not choose a preferred proposal",
            "artifact does not dispatch execution",
            "artifact does not enforce structural influence",
            "artifact does not evaluate proposal quality",
            "artifact does not load adapters",
            "artifact does not load models",
            "artifact does not order proposals by preference",
        ]),
    }

    semantic_payload = {
        "artifact_class": artifact["artifact_class"],
        "authorized_proposal_digests": artifact[
            "authorized_proposal_digests"
        ],
        "consumer_class": artifact["consumer_class"],
        "materialization_class": artifact["materialization_class"],
        "target_domain_class": artifact["target_domain_class"],
        "application_state": artifact["application_state"],
        "source_capability_digest": artifact["source_capability_digest"],
        "source_capability_semantic_digest": artifact[
            "source_capability_semantic_digest"
        ],
        "structural_influence_scope_digest": artifact[
            "structural_influence_scope_digest"
        ],
        "proposal_bindings": artifact["proposal_bindings"],
        "consumption_request_digest": artifact[
            "consumption_request_digest"
        ],
        "compiler_contract_digest": artifact[
            "compiler_contract_digest"
        ],
    }
    artifact["artifact_semantic_digest"] = canonical_digest(
        semantic_payload
    )
    artifact["artifact_digest"] = canonical_digest({
        key: value
        for key, value in artifact.items()
        if key != "artifact_digest"
    })
    return artifact


def _authority_objects(artifact: dict):
    chain = SourceChain(
        g53b1=_phase("G5.3B.1"),
        g53c=_phase(
            "G5.3C",
            artifact_digest=artifact["artifact_digest"],
            capability_digest=artifact["source_capability_digest"],
            lifecycle_state="GRANTED_UNCONSUMED",
            receipt=_h("application-receipt"),
            state=_h("resulting-state"),
            ledger=_h("source-application-ledger"),
        ),
        g53d=_phase("G5.3D"),
    )

    decision = PromotionDecision(
        decision=DECISION_READY,
        gate_vector=(_h("gate-1"), _h("gate-2")),
        source_chain_digest=chain.chain_digest,
        expected_canonical_preconditions=PRECONDITIONS,
    )

    plan = CanonicalPromotionPlan(
        intentions=INTENTIONS,
        decision_digest=decision.digest,
        source_chain_digest=chain.chain_digest,
    )
    return chain, decision, plan


def _issue(
    current: Path,
    ledger: DurableApplicationLedger,
    artifact: dict,
    approval_label: str,
):
    chain, decision, plan = _authority_objects(artifact)
    return issue_promotion_capability(
        plan=plan,
        decision=decision,
        chain=chain,
        project_root=current,
        operator_approval_digest=_h(approval_label),
        expected_publication_ledger_head=ledger.head,
    )


def test_grid81_canonical_writer_chain_golden_publish_and_exact_replay(
    tmp_path,
):
    current = _copy_root(tmp_path, "live")
    live_grid = current / "Canonical" / "Grid81"
    candidate = tmp_path / "candidate"
    artifact = _artifact()

    live_before = _tree_map(live_grid)
    historical_before = (
        live_grid / "generations" / "000001.json"
    ).read_bytes()
    canonical_before = load_current_grid81(current)

    with DurableApplicationLedger(
        tmp_path / "publication-ledger.sqlite3"
    ) as ledger:
        cap = _issue(current, ledger, artifact, "operator-A")
        initial_ledger_head = ledger.head

        constructed = construct_candidate(
            project_root=current,
            candidate_root=candidate,
            promotion_capability=cap,
            structural_artifact=artifact,
        )

        # Candidate construction is non-live and non-consuming.
        assert _tree_map(live_grid) == live_before
        assert ledger.is_empty
        assert ledger.head == initial_ledger_head
        assert load_current_grid81(current).canonical_digest == (
            canonical_before.canonical_digest
        )

        candidate_state = load_current_grid81(candidate)
        assert candidate_state.generation_number == (
            canonical_before.generation_number + 1
        )
        assert candidate_state.transaction_id == (
            cap["target_bindings"]["transaction_id"]
        )
        assert candidate_state.capability_id == cap["capability_id"]
        assert constructed.candidate_canonical_digest == (
            candidate_state.canonical_digest
        )

        # Historical canonical generations survive candidate construction
        # exactly, before any publication occurs.
        assert (
            candidate
            / "Canonical"
            / "Grid81"
            / "generations"
            / "000001.json"
        ).read_bytes() == historical_before

        published = publish_candidate(
            project_root=current,
            candidate_root=candidate,
            ledger=ledger,
            promotion_capability=cap,
            lock_path=current / "Canonical",
        )

        committed = load_current_grid81(current)
        assert published.status == "COMMITTED"
        assert published.resumed is False
        assert committed.generation_number == 2
        assert committed.canonical_digest == (
            constructed.candidate_canonical_digest
        )
        assert committed.transaction_id == (
            cap["target_bindings"]["transaction_id"]
        )
        assert committed.capability_id == cap["capability_id"]

        assert ledger.to_dict()["count"] == 1
        assert ledger.has_receipt(artifact["artifact_digest"])
        assert not ledger.has_receipt(cap["capability_digest"])
        committed_ledger_head = ledger.head
        assert committed_ledger_head != initial_ledger_head

        # Publication must preserve all prior generation bytes exactly.
        assert (
            live_grid / "generations" / "000001.json"
        ).read_bytes() == historical_before

        # A distinct otherwise-valid promotion capability cannot replay
        # the already committed candidate.
        wrong_cap = _issue(
            _copy_root(tmp_path, "alternate-source"),
            DurableApplicationLedger(
                tmp_path / "alternate-publication-ledger.sqlite3"
            ),
            artifact,
            "operator-B",
        )
        # Rebind wrong_cap to the original publication-ledger prestate by
        # issuing through a separate source copy with the same canonical
        # generation but distinct operator approval.  It remains a valid
        # capability object, but its transaction/capability identity differs.
        with pytest.raises(
            PublicationError,
            match=(
                "PROMOTION_TRANSACTION_ID_MISMATCH"
                "|PROMOTION_CAPABILITY_ID_MISMATCH"
            ),
        ):
            publish_candidate(
                project_root=current,
                candidate_root=candidate,
                ledger=ledger,
                promotion_capability=wrong_cap,
                lock_path=current / "Canonical",
            )

        assert ledger.to_dict()["count"] == 1
        assert ledger.head == committed_ledger_head
        assert load_current_grid81(current).canonical_digest == (
            committed.canonical_digest
        )

        # Exact original capability replay is idempotent.
        replay = publish_candidate(
            project_root=current,
            candidate_root=candidate,
            ledger=ledger,
            promotion_capability=cap,
            lock_path=current / "Canonical",
        )

        assert replay.status == "ALREADY_COMMITTED"
        assert replay.resumed is True
        assert ledger.to_dict()["count"] == 1
        assert ledger.head == committed_ledger_head
        assert load_current_grid81(current).canonical_digest == (
            committed.canonical_digest
        )


def test_writer_chain_rejects_cross_structural_capability_relation(
    tmp_path,
):
    current = _copy_root(tmp_path, "live")
    artifact = _artifact()

    with DurableApplicationLedger(
        tmp_path / "publication-ledger.sqlite3"
    ) as ledger:
        chain, decision, plan = _authority_objects(artifact)
        chain = SourceChain(
            g53b1=chain.g53b1,
            g53c=PhaseEvidence(
                phase_id=chain.g53c.phase_id,
                source_directory=chain.g53c.source_directory,
                manifest_path=chain.g53c.manifest_path,
                manifest_digest=chain.g53c.manifest_digest,
                disposition=chain.g53c.disposition,
                evidence_files=chain.g53c.evidence_files,
                artifact_digest=chain.g53c.artifact_digest,
                capability_digest=_h("wrong-structural-capability"),
                lifecycle_state=chain.g53c.lifecycle_state,
                shadow_receipt_digest=chain.g53c.shadow_receipt_digest,
                resulting_state_digest=chain.g53c.resulting_state_digest,
                resulting_ledger_head=chain.g53c.resulting_ledger_head,
                bundle_digest=chain.g53c.bundle_digest,
            ),
            g53d=chain.g53d,
        )
        decision = PromotionDecision(
            decision=DECISION_READY,
            gate_vector=decision.gate_vector,
            source_chain_digest=chain.chain_digest,
            expected_canonical_preconditions=PRECONDITIONS,
        )
        plan = CanonicalPromotionPlan(
            intentions=INTENTIONS,
            decision_digest=decision.digest,
            source_chain_digest=chain.chain_digest,
        )

        cap = issue_promotion_capability(
            plan=plan,
            decision=decision,
            chain=chain,
            project_root=current,
            operator_approval_digest=_h("operator-A"),
            expected_publication_ledger_head=ledger.head,
        )

        from elpis_grid81_candidate_constructor import (
            CandidateConstructionError,
        )

        with pytest.raises(
            CandidateConstructionError,
            match="ARTIFACT_STRUCTURAL_CAPABILITY_BINDING_MISMATCH",
        ):
            construct_candidate(
                project_root=current,
                candidate_root=tmp_path / "candidate",
                promotion_capability=cap,
                structural_artifact=artifact,
            )

        assert ledger.is_empty
        assert load_current_grid81(current).generation_number == 1
