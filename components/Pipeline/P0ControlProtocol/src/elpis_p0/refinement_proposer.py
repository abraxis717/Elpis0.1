"""Phase E — Versioned refinement proposer protocol.

Defines the proposer interface that consumes P0RefinementInputV1 rather
than raw projection/grid/mask. Proposals bind to the envelope digest.
"""
from __future__ import annotations

from typing import Protocol

from .contracts import (
    P0RefinementInputV1,
    TRMRefinementProposal,
)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class RefinementProposerPort(Protocol):
    """Versioned refinement proposer that takes P0RefinementInputV1.

    The proposer consumes the envelope (which includes the controller-owned
    scope mask) and produces a TRMRefinementProposal bound to the envelope
    digest — NOT the projection digest, grid digest, or structural digest.
    """

    proposer_id: str
    proposer_version: str

    def propose_refinement(
        self,
        input_envelope: P0RefinementInputV1,
    ) -> TRMRefinementProposal:
        ...


# ---------------------------------------------------------------------------
# Deterministic shadow proposer for Gate 2
# ---------------------------------------------------------------------------

import hashlib
import json
from typing import Any, Literal

from .canonical import digest


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


ShadowFixtureMode = Literal[
    "NOOP",
    "ONE_WRITABLE_EDIT",
    "ONE_LOCKED_EDIT",
    "MULTIPLE_EDITS",
    "WRONG_INPUT_DIGEST",
    "INVALID_TOKEN",
]


class DeterministicShadowRefinementProposer:
    """Deterministic proposer that consumes P0RefinementInputV1.

    Binds proposal to envelope_digest. Produces predictable outputs
    for test fixture modes. No model loading, no random sampling,
    no scope inference, no world mutation.
    """

    proposer_id: str = "shadow-refinement.v1"
    proposer_version: str = "g2.0.deterministic"

    def __init__(
        self,
        fixture_mode: ShadowFixtureMode = "ONE_WRITABLE_EDIT",
    ) -> None:
        self._fixture_mode = fixture_mode

    def propose_refinement(
        self,
        input_envelope: P0RefinementInputV1,
    ) -> TRMRefinementProposal:
        """Produce a deterministic proposal bound to the envelope digest."""
        si = input_envelope.structural_input
        grid = list(si.grid81)
        mask = si.writable_mask81

        if self._fixture_mode == "NOOP":
            # No changes
            proposed = tuple(grid)

        elif self._fixture_mode == "ONE_WRITABLE_EDIT":
            # Edit first writable cell
            proposed = self._one_writable_edit(grid, mask)

        elif self._fixture_mode == "ONE_LOCKED_EDIT":
            # Edit first locked (non-writable) cell — should fail scope check
            proposed = self._one_locked_edit(grid, mask)

        elif self._fixture_mode == "MULTIPLE_EDITS":
            # Edit two cells — should fail single-edit locality
            proposed = self._multiple_edits(grid, mask)

        elif self._fixture_mode == "WRONG_INPUT_DIGEST":
            # Produce proposal bound to wrong digest
            proposed = self._one_writable_edit(grid, mask)
            return TRMRefinementProposal(
                input_digest="0" * 64,  # intentionally wrong
                proposed_grid81=proposed,
                residual81=tuple(0.125 for _ in grid),
                halt_score=0.5,
                expansion_cells=(),
                rationale=("fixture:wrong_digest",),
                digest=_sha256_hex(
                    _canonical_bytes({
                        "input_digest": "0" * 64,
                        "proposed_grid81": list(proposed),
                    })
                ),
            )

        elif self._fixture_mode == "INVALID_TOKEN":
            # Place token outside 0..9 domain
            proposed = self._invalid_token(grid, mask)

        else:
            raise ValueError(f"Unknown fixture mode: {self._fixture_mode!r}")

        proposal_payload = {
            "input_digest": input_envelope.envelope_digest,
            "proposed_grid81": list(proposed),
        }
        proposal_digest = _sha256_hex(_canonical_bytes(proposal_payload))

        return TRMRefinementProposal(
            input_digest=input_envelope.envelope_digest,
            proposed_grid81=proposed,
            residual81=tuple(0.125 for _ in grid),
            halt_score=0.5,
            expansion_cells=(),
            rationale=(f"fixture:{self._fixture_mode}",),
            digest=proposal_digest,
        )

    @staticmethod
    def _one_writable_edit(
        grid: list[int], mask: tuple[int, ...]
    ) -> tuple[int, ...]:
        for i in range(81):
            if mask[i] == 1:
                new_grid = list(grid)
                new_grid[i] = (grid[i] + 1) % 10
                return tuple(new_grid)
        # No writable cell — fall through to noop
        return tuple(grid)

    @staticmethod
    def _one_locked_edit(
        grid: list[int], mask: tuple[int, ...]
    ) -> tuple[int, ...]:
        for i in range(81):
            if mask[i] == 0:
                new_grid = list(grid)
                new_grid[i] = (grid[i] + 1) % 10
                return tuple(new_grid)
        # All cells writable — should not happen in normal tests
        return tuple(grid)

    @staticmethod
    def _multiple_edits(
        grid: list[int], mask: tuple[int, ...]
    ) -> tuple[int, ...]:
        new_grid = list(grid)
        count = 0
        for i in range(81):
            if mask[i] == 1 and count < 2:
                new_grid[i] = (grid[i] + 1) % 10
                count += 1
        return tuple(new_grid)

    @staticmethod
    def _invalid_token(
        grid: list[int], mask: tuple[int, ...]
    ) -> tuple[int, ...]:
        for i in range(81):
            if mask[i] == 1:
                new_grid = list(grid)
                new_grid[i] = 99  # outside 0..9
                return tuple(new_grid)
        return tuple(grid)
