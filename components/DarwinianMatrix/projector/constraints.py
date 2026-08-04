"""Deterministic task-scoped Grid81 clamp transactions.

This module defines projector-owned structural constraints. It does not call
the TRM and does not inspect ecological state.

Accepted transactions produce a new clamp state. Rejected transactions return
the original state unchanged with a deterministic receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Iterable

import torch
from torch import Tensor

from ..geometry import GRID_CELLS


CLAMP_STATE_SCHEMA = "darwinian.clamp-state.v1"
CLAMP_TRANSACTION_SCHEMA = "darwinian.clamp-transaction.v1"
CLAMP_RECEIPT_SCHEMA = "darwinian.clamp-receipt.v1"

TRANSACTION_ACCEPTED = "CLAMP_TRANSACTION_ACCEPTED"
TRANSACTION_REJECTED = "CLAMP_TRANSACTION_REJECTED"


class ClampOperation(str, Enum):
    ASSERT = "ASSERT"
    REPLACE = "REPLACE"
    RELEASE = "RELEASE"


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _domain_digest(domain: str, payload: object) -> str:
    return hashlib.sha256(
        domain.encode("utf-8")
        + b"\x00"
        + _canonical_json_bytes(payload)
    ).hexdigest()


def _require_digest(name: str, value: str) -> None:
    if len(value) != 64:
        raise ValueError(
            f"{name} must be a 64-character SHA-256 digest."
        )

    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be hexadecimal."
        ) from exc


@dataclass(frozen=True)
class ClampProposal:
    proposal_id: str
    operation: ClampOperation
    slot_id: str
    evidence_digest: str
    cell_index: int
    value: int | None = None

    def __post_init__(self) -> None:
        if not self.proposal_id:
            raise ValueError(
                "proposal_id cannot be empty."
            )

        if not self.slot_id:
            raise ValueError(
                "slot_id cannot be empty."
            )

        _require_digest(
            "evidence_digest",
            self.evidence_digest,
        )

        if not 0 <= self.cell_index < GRID_CELLS:
            raise ValueError(
                f"cell_index must be in [0, {GRID_CELLS - 1}]."
            )

        if self.operation in (
            ClampOperation.ASSERT,
            ClampOperation.REPLACE,
        ):
            if self.value is None:
                raise ValueError(
                    f"{self.operation.value} requires a value."
                )

            if not 1 <= self.value <= 9:
                raise ValueError(
                    "Clamp values must remain within 1..9."
                )

        elif self.operation == ClampOperation.RELEASE:
            if self.value is not None:
                raise ValueError(
                    "RELEASE must not contain a value."
                )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "cell_index": self.cell_index,
            "evidence_digest": self.evidence_digest,
            "operation": self.operation.value,
            "proposal_id": self.proposal_id,
            "slot_id": self.slot_id,
            "value": self.value,
        }

    def digest(self) -> str:
        return _domain_digest(
            "darwinian.clamp-proposal.v1",
            self.canonical_payload(),
        )


@dataclass(frozen=True)
class ClampTransaction:
    transaction_id: str
    episode_id: str
    expected_state_digest: str
    proposals: tuple[ClampProposal, ...] = ()
    close_episode: bool = False

    def __post_init__(self) -> None:
        if not self.transaction_id:
            raise ValueError(
                "transaction_id cannot be empty."
            )

        if not self.episode_id:
            raise ValueError(
                "episode_id cannot be empty."
            )

        _require_digest(
            "expected_state_digest",
            self.expected_state_digest,
        )

        if self.close_episode and self.proposals:
            raise ValueError(
                "Episode close must be a dedicated transaction "
                "with no proposals."
            )

    @property
    def canonical_proposals(
        self,
    ) -> tuple[ClampProposal, ...]:
        return tuple(
            sorted(
                self.proposals,
                key=lambda proposal: proposal.proposal_id,
            )
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "close_episode": self.close_episode,
            "episode_id": self.episode_id,
            "expected_state_digest": (
                self.expected_state_digest
            ),
            "proposals": [
                proposal.canonical_payload()
                for proposal in self.canonical_proposals
            ],
            "schema_version": CLAMP_TRANSACTION_SCHEMA,
            "transaction_id": self.transaction_id,
        }

    def digest(self) -> str:
        return _domain_digest(
            CLAMP_TRANSACTION_SCHEMA,
            self.canonical_payload(),
        )


class ClampState:
    """Persistent projector-owned Grid81 clamp constellation."""

    __slots__ = (
        "_episode_id",
        "_version",
        "_closed",
        "_active_mask",
        "_values",
        "_owners",
    )

    def __init__(
        self,
        *,
        episode_id: str,
        version: int = 0,
        closed: bool = False,
        active_mask: Tensor | None = None,
        values: Tensor | None = None,
        owners: Iterable[str | None] | None = None,
    ) -> None:
        if not episode_id:
            raise ValueError(
                "episode_id cannot be empty."
            )

        if version < 0:
            raise ValueError(
                "version cannot be negative."
            )

        self._episode_id = episode_id
        self._version = int(version)
        self._closed = bool(closed)

        if active_mask is None:
            active_mask = torch.zeros(
                GRID_CELLS,
                dtype=torch.bool,
            )

        if values is None:
            values = torch.zeros(
                GRID_CELLS,
                dtype=torch.int8,
            )

        if owners is None:
            owners = (None,) * GRID_CELLS

        self._active_mask = active_mask.detach().to(
            device="cpu",
            dtype=torch.bool,
        ).reshape(-1).clone()

        self._values = values.detach().to(
            device="cpu",
            dtype=torch.int8,
        ).reshape(-1).clone()

        self._owners = tuple(owners)

        self._validate()

    @classmethod
    def empty(cls, episode_id: str) -> "ClampState":
        return cls(episode_id=episode_id)

    @property
    def episode_id(self) -> str:
        return self._episode_id

    @property
    def version(self) -> int:
        return self._version

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def active_mask(self) -> Tensor:
        return self._active_mask.clone()

    @property
    def values(self) -> Tensor:
        return self._values.clone()

    @property
    def owners(self) -> tuple[str | None, ...]:
        return tuple(self._owners)

    @property
    def active_count(self) -> int:
        return int(
            self._active_mask.sum().item()
        )

    def _validate(self) -> None:
        if self._active_mask.shape != (GRID_CELLS,):
            raise ValueError(
                "active_mask must have shape (81,)."
            )

        if self._values.shape != (GRID_CELLS,):
            raise ValueError(
                "values must have shape (81,)."
            )

        if len(self._owners) != GRID_CELLS:
            raise ValueError(
                "owners must contain 81 entries."
            )

        inactive = ~self._active_mask
        active = self._active_mask

        if bool(self._values[inactive].ne(0).any()):
            raise ValueError(
                "Inactive clamp cells must have value zero."
            )

        if bool(
            (
                active
                & (
                    (self._values < 1)
                    | (self._values > 9)
                )
            ).any()
        ):
            raise ValueError(
                "Active clamp values must remain within 1..9."
            )

        for index, owner in enumerate(self._owners):
            if bool(self._active_mask[index]):
                if not isinstance(owner, str) or not owner:
                    raise ValueError(
                        "Every active clamp must have an owner."
                    )
            elif owner is not None:
                raise ValueError(
                    "Inactive clamp cells cannot have owners."
                )

        if self._closed and self.active_count != 0:
            raise ValueError(
                "Closed clamp state must contain no active clamps."
            )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "active_mask": [
                bool(value)
                for value in self._active_mask.tolist()
            ],
            "closed": self._closed,
            "episode_id": self._episode_id,
            "owners": list(self._owners),
            "schema_version": CLAMP_STATE_SCHEMA,
            "values": [
                int(value)
                for value in self._values.tolist()
            ],
            "version": self._version,
        }

    def digest(self) -> str:
        return _domain_digest(
            CLAMP_STATE_SCHEMA,
            self.canonical_payload(),
        )

    def trm_inputs(
        self,
        *,
        device: str | torch.device = "cpu",
    ) -> tuple[Tensor, Tensor]:
        """Return detached clamp values and mask for the frozen TRM."""
        return (
            self._values.to(
                device=device,
                dtype=torch.int64,
            ).clone(),
            self._active_mask.to(
                device=device,
                dtype=torch.bool,
            ).clone(),
        )


@dataclass(frozen=True)
class ClampTransactionReceipt:
    outcome: str
    reason_codes: tuple[str, ...]

    transaction_digest: str
    state_before_digest: str
    state_after_digest: str

    committed_proposal_digests: tuple[str, ...]
    resulting_version: int
    resulting_active_count: int
    episode_closed: bool

    receipt_digest: str

    def __post_init__(self) -> None:
        if self.outcome not in (
            TRANSACTION_ACCEPTED,
            TRANSACTION_REJECTED,
        ):
            raise ValueError(
                "Unsupported clamp transaction outcome."
            )

        if not self.reason_codes:
            raise ValueError(
                "Receipt requires at least one reason code."
            )

        if tuple(
            sorted(set(self.reason_codes))
        ) != self.reason_codes:
            raise ValueError(
                "reason_codes must be sorted and unique."
            )

        for name in (
            "transaction_digest",
            "state_before_digest",
            "state_after_digest",
            "receipt_digest",
        ):
            _require_digest(
                name,
                getattr(self, name),
            )

        for digest in self.committed_proposal_digests:
            _require_digest(
                "committed proposal digest",
                digest,
            )

    def semantic_payload(self) -> dict[str, object]:
        return {
            "committed_proposal_digests": list(
                self.committed_proposal_digests
            ),
            "episode_closed": self.episode_closed,
            "outcome": self.outcome,
            "reason_codes": list(self.reason_codes),
            "resulting_active_count": (
                self.resulting_active_count
            ),
            "resulting_version": self.resulting_version,
            "schema_version": CLAMP_RECEIPT_SCHEMA,
            "state_after_digest": self.state_after_digest,
            "state_before_digest": self.state_before_digest,
            "transaction_digest": self.transaction_digest,
        }

    def recompute_digest(self) -> str:
        return _domain_digest(
            CLAMP_RECEIPT_SCHEMA,
            self.semantic_payload(),
        )

    def validate_digest(self) -> bool:
        return (
            self.receipt_digest
            == self.recompute_digest()
        )


@dataclass(frozen=True)
class ClampTransactionResult:
    state: ClampState
    receipt: ClampTransactionReceipt

    @property
    def accepted(self) -> bool:
        return (
            self.receipt.outcome
            == TRANSACTION_ACCEPTED
        )


def _build_receipt(
    *,
    outcome: str,
    reason_codes: tuple[str, ...],
    transaction: ClampTransaction,
    before_state: ClampState,
    after_state: ClampState,
    committed_proposals: tuple[ClampProposal, ...],
) -> ClampTransactionReceipt:
    partial = ClampTransactionReceipt(
        outcome=outcome,
        reason_codes=tuple(
            sorted(set(reason_codes))
        ),
        transaction_digest=transaction.digest(),
        state_before_digest=before_state.digest(),
        state_after_digest=after_state.digest(),
        committed_proposal_digests=tuple(
            proposal.digest()
            for proposal in committed_proposals
        ),
        resulting_version=after_state.version,
        resulting_active_count=after_state.active_count,
        episode_closed=after_state.closed,
        receipt_digest="0" * 64,
    )

    return ClampTransactionReceipt(
        outcome=partial.outcome,
        reason_codes=partial.reason_codes,
        transaction_digest=partial.transaction_digest,
        state_before_digest=partial.state_before_digest,
        state_after_digest=partial.state_after_digest,
        committed_proposal_digests=(
            partial.committed_proposal_digests
        ),
        resulting_version=partial.resulting_version,
        resulting_active_count=(
            partial.resulting_active_count
        ),
        episode_closed=partial.episode_closed,
        receipt_digest=partial.recompute_digest(),
    )


def _reject(
    *,
    state: ClampState,
    transaction: ClampTransaction,
    reason_code: str,
) -> ClampTransactionResult:
    receipt = _build_receipt(
        outcome=TRANSACTION_REJECTED,
        reason_codes=(reason_code,),
        transaction=transaction,
        before_state=state,
        after_state=state,
        committed_proposals=(),
    )

    return ClampTransactionResult(
        state=state,
        receipt=receipt,
    )


def apply_clamp_transaction(
    *,
    state: ClampState,
    transaction: ClampTransaction,
) -> ClampTransactionResult:
    """Apply one atomic projector clamp transaction."""
    if transaction.episode_id != state.episode_id:
        return _reject(
            state=state,
            transaction=transaction,
            reason_code="EPISODE_ID_MISMATCH",
        )

    if transaction.expected_state_digest != state.digest():
        return _reject(
            state=state,
            transaction=transaction,
            reason_code="STALE_CLAMP_STATE",
        )

    if state.closed:
        return _reject(
            state=state,
            transaction=transaction,
            reason_code="CLAMP_STATE_CLOSED",
        )

    proposal_ids = [
        proposal.proposal_id
        for proposal in transaction.proposals
    ]

    if len(set(proposal_ids)) != len(proposal_ids):
        return _reject(
            state=state,
            transaction=transaction,
            reason_code="DUPLICATE_PROPOSAL_ID",
        )

    target_cells = [
        proposal.cell_index
        for proposal in transaction.proposals
    ]

    if len(set(target_cells)) != len(target_cells):
        return _reject(
            state=state,
            transaction=transaction,
            reason_code="DUPLICATE_CELL_TARGET",
        )

    if transaction.close_episode:
        next_state = ClampState(
            episode_id=state.episode_id,
            version=state.version + 1,
            closed=True,
        )

        receipt = _build_receipt(
            outcome=TRANSACTION_ACCEPTED,
            reason_codes=(
                "META_EPISODE_CLOSED",
                "TASK_CLAMPS_RELEASED",
            ),
            transaction=transaction,
            before_state=state,
            after_state=next_state,
            committed_proposals=(),
        )

        return ClampTransactionResult(
            state=next_state,
            receipt=receipt,
        )

    active_mask = state.active_mask
    values = state.values
    owners = list(state.owners)

    proposals = transaction.canonical_proposals

    for proposal in proposals:
        index = proposal.cell_index
        active = bool(active_mask[index])
        owner = owners[index]

        if proposal.operation == ClampOperation.ASSERT:
            if active:
                return _reject(
                    state=state,
                    transaction=transaction,
                    reason_code="ASSERT_TARGET_OCCUPIED",
                )

            active_mask[index] = True
            values[index] = int(proposal.value)
            owners[index] = proposal.slot_id

        elif proposal.operation == ClampOperation.REPLACE:
            if not active:
                return _reject(
                    state=state,
                    transaction=transaction,
                    reason_code="REPLACE_TARGET_INACTIVE",
                )

            if owner != proposal.slot_id:
                return _reject(
                    state=state,
                    transaction=transaction,
                    reason_code="CLAMP_OWNER_MISMATCH",
                )

            values[index] = int(proposal.value)

        elif proposal.operation == ClampOperation.RELEASE:
            if not active:
                return _reject(
                    state=state,
                    transaction=transaction,
                    reason_code="RELEASE_TARGET_INACTIVE",
                )

            if owner != proposal.slot_id:
                return _reject(
                    state=state,
                    transaction=transaction,
                    reason_code="CLAMP_OWNER_MISMATCH",
                )

            active_mask[index] = False
            values[index] = 0
            owners[index] = None

    next_state = ClampState(
        episode_id=state.episode_id,
        version=state.version + 1,
        closed=False,
        active_mask=active_mask,
        values=values,
        owners=owners,
    )

    receipt = _build_receipt(
        outcome=TRANSACTION_ACCEPTED,
        reason_codes=("CLAMP_TRANSACTION_COMMITTED",),
        transaction=transaction,
        before_state=state,
        after_state=next_state,
        committed_proposals=proposals,
    )

    return ClampTransactionResult(
        state=next_state,
        receipt=receipt,
    )
