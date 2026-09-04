from __future__ import annotations

from dataclasses import replace
import inspect
from pathlib import Path
from typing import get_type_hints

import pytest

from elpis_reference.structural_guidance import (
    RESOLVED_TOPOLOGY_CONSUMER_RECEIPT_SCHEMA,
    ResolvedStructuralTopologyV1,
    ResolvedTopologyConsumerContractError,
    ResolvedTopologyConsumerPort,
    ResolvedTopologyConsumerReceiptV1,
)


TOPOLOGY_DIGEST = "a" * 64


def test_observed_receipt_is_authority_zero():
    receipt = (
        ResolvedTopologyConsumerReceiptV1
        .observed(
            topology_digest=TOPOLOGY_DIGEST,
            consumer_id="test.consumer",
            consumer_version="v1",
        )
    )

    assert (
        receipt.schema
        == RESOLVED_TOPOLOGY_CONSUMER_RECEIPT_SCHEMA
    )
    assert receipt.outcome == "OBSERVED"
    assert receipt.topology_digest == TOPOLOGY_DIGEST

    assert receipt.authority_granted == 0
    assert receipt.execution_authorized is False
    assert receipt.decoding_authorized is False
    assert (
        receipt.materialization_authorized
        is False
    )

    assert receipt.validate_digest()


def test_rejected_receipt_also_grants_nothing():
    receipt = (
        ResolvedTopologyConsumerReceiptV1
        .rejected(
            topology_digest=TOPOLOGY_DIGEST,
            consumer_id="test.consumer",
            consumer_version="v1",
        )
    )

    assert receipt.outcome == "REJECTED"
    assert receipt.authority_granted == 0
    assert receipt.execution_authorized is False
    assert receipt.decoding_authorized is False
    assert (
        receipt.materialization_authorized
        is False
    )
    assert receipt.validate_digest()


@pytest.mark.parametrize(
    (
        "field",
        "value",
        "match",
    ),
    (
        (
            "authority_granted",
            1,
            "authority",
        ),
        (
            "execution_authorized",
            True,
            "execution",
        ),
        (
            "decoding_authorized",
            True,
            "decoding",
        ),
        (
            "materialization_authorized",
            True,
            "materialization",
        ),
    ),
)
def test_receipt_refuses_authority_widening(
    field,
    value,
    match,
):
    receipt = (
        ResolvedTopologyConsumerReceiptV1
        .observed(
            topology_digest=TOPOLOGY_DIGEST,
            consumer_id="test.consumer",
            consumer_version="v1",
        )
    )

    with pytest.raises(
        ResolvedTopologyConsumerContractError,
        match=match,
    ):
        replace(
            receipt,
            **{
                field: value,
                "receipt_digest": "",
            },
        )


def test_receipt_digest_detects_tamper():
    receipt = (
        ResolvedTopologyConsumerReceiptV1
        .observed(
            topology_digest=TOPOLOGY_DIGEST,
            consumer_id="test.consumer",
            consumer_version="v1",
        )
    )

    object.__setattr__(
        receipt,
        "consumer_version",
        "v2",
    )

    assert not receipt.validate_digest()


def test_port_surface_is_observation_only():
    public_methods = {
        name
        for name, value in inspect.getmembers(
            ResolvedTopologyConsumerPort
        )
        if not name.startswith("_")
        and inspect.isfunction(value)
    }

    assert public_methods == {
        "observe",
    }

    signature = inspect.signature(
        ResolvedTopologyConsumerPort.observe
    )

    assert tuple(
        signature.parameters
    ) == (
        "self",
        "topology",
    )

    hints = get_type_hints(
        ResolvedTopologyConsumerPort.observe
    )

    assert (
        hints["topology"]
        is ResolvedStructuralTopologyV1
    )

    assert (
        hints["return"]
        is ResolvedTopologyConsumerReceiptV1
    )


def test_consumer_contract_has_no_execution_imports():
    import elpis_reference.structural_guidance.consumer as consumer

    source = Path(
        consumer.__file__
    ).read_text().lower()

    forbidden_imports = (
        "darwinianmatrix",
        "darwinian_matrix",
        "p01_materializer",
        "reference_solver",
        "elpis_p0",
        "p0controller",
        ".decoder",
        "artifactcandidate",
        "decodercontrolplan",
        "torch",
        "subprocess",
        "runpy",
        "importlib",
    )

    for token in forbidden_imports:
        assert token not in source


def test_consumer_port_cannot_emit_execution_artifact():
    signature = inspect.signature(
        ResolvedTopologyConsumerPort.observe
    )

    encoded = str(
        signature.return_annotation
    ).lower()

    for forbidden in (
        "artifactcandidate",
        "decodercontrolplan",
        "p0result",
        "source",
        "plan",
    ):
        assert forbidden not in encoded
