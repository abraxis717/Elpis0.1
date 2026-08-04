"""P14.2c trigger-first Markov header reference implementation.

Specification:
- Header is exactly 16 bytes.
- Inter-token transition consumes only a preclassified token effect.
- No retrieval, graph traversal, model inference, filesystem access, dynamic
  packet derivation, or evidence serialization belongs in ``transition``.
- Token text compilation occurs outside the hot path.
- Token effects compose as endomorphisms over the finite header state.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import IntEnum, IntFlag
import struct
from typing import Iterable


HEADER_STRUCT = struct.Struct("<BBBBhHHHBBH")
HEADER_BYTES = HEADER_STRUCT.size
HEADER_VERSION = 1
MAX_JSON_DEPTH = 15


class Regime(IntEnum):
    NEUTRAL = 0
    CODING = 1
    JSON_ACTION = 2
    RECOVERY = 3
    STOP = 4


class Phase(IntEnum):
    START = 0
    JSON = 1
    STRING = 2
    ESCAPE = 3
    COMPLETE = 4
    INVALID = 5


class TokenClass(IntEnum):
    OTHER = 0
    WHITESPACE = 1
    OPEN_BRACE = 2
    CLOSE_BRACE = 3
    QUOTE = 4
    BACKSLASH = 5
    EOS = 6
    REPETITION = 7
    BUDGET = 8


class ConstraintFlag(IntFlag):
    NONE = 0
    REQUIRE_BARE_JSON = 1 << 0
    JSON_STARTED = 1 << 1
    IN_STRING = 1 << 2
    ESCAPE_PENDING = 1 << 3
    JSON_COMPLETE = 1 << 4


class TriggerFlag(IntFlag):
    NONE = 0
    JSON_OPENED = 1 << 0
    JSON_CLOSED = 1 << 1
    INVALID_PREFIX = 1 << 2
    EOS = 1 << 3
    REPETITION = 1 << 4
    TOKEN_BUDGET = 1 << 5
    DEPTH_OVERFLOW = 1 << 6
    INCOMPLETE_EOS = 1 << 7


@dataclass(frozen=True, slots=True)
class MarkovHeader:
    version: int = HEADER_VERSION
    regime: int = int(Regime.CODING)
    phase: int = int(Phase.START)
    residual_slot: int = 0
    gain_q15: int = 0
    constraint_flags: int = int(ConstraintFlag.REQUIRE_BARE_JSON)
    trigger_flags: int = 0
    residence: int = 0
    json_depth: int = 0
    token_class: int = int(TokenClass.OTHER)
    sequence: int = 0

    def __post_init__(self) -> None:
        if self.version != HEADER_VERSION:
            raise ValueError("header version mismatch")
        if not 0 <= self.regime <= 255:
            raise ValueError("regime outside uint8")
        if not 0 <= self.phase <= 255:
            raise ValueError("phase outside uint8")
        if not 0 <= self.residual_slot <= 255:
            raise ValueError("residual_slot outside uint8")
        if not -32768 <= self.gain_q15 <= 32767:
            raise ValueError("gain_q15 outside int16")
        for name in ("constraint_flags", "trigger_flags", "residence", "sequence"):
            if not 0 <= int(getattr(self, name)) <= 65535:
                raise ValueError(f"{name} outside uint16")
        if not 0 <= self.json_depth <= 255:
            raise ValueError("json_depth outside uint8")
        if not 0 <= self.token_class <= 255:
            raise ValueError("token_class outside uint8")

    def pack(self) -> bytes:
        value = HEADER_STRUCT.pack(
            self.version,
            self.regime,
            self.phase,
            self.residual_slot,
            self.gain_q15,
            self.constraint_flags,
            self.trigger_flags,
            self.residence,
            self.json_depth,
            self.token_class,
            self.sequence,
        )
        if len(value) != HEADER_BYTES:
            raise AssertionError("packed header width drift")
        return value

    @classmethod
    def unpack(cls, value: bytes) -> "MarkovHeader":
        if len(value) != HEADER_BYTES:
            raise ValueError("packed header must be exactly 16 bytes")
        return cls(*HEADER_STRUCT.unpack(value))


def transition(header: MarkovHeader, token_class: TokenClass) -> MarkovHeader:
    """Pure fixed-width transition over an already-classified token."""
    if header.regime == int(Regime.STOP):
        return replace(
            header,
            token_class=int(token_class),
            sequence=(header.sequence + 1) & 0xFFFF,
        )

    phase = Phase(header.phase)
    constraints = ConstraintFlag(header.constraint_flags)
    triggers = TriggerFlag(header.trigger_flags)
    regime = Regime(header.regime)
    depth = header.json_depth
    residence = min(65535, header.residence + 1)

    if token_class is TokenClass.EOS:
        triggers |= TriggerFlag.EOS
        if phase is not Phase.COMPLETE:
            triggers |= TriggerFlag.INCOMPLETE_EOS
        regime = Regime.STOP

    elif token_class is TokenClass.REPETITION:
        triggers |= TriggerFlag.REPETITION
        regime = Regime.RECOVERY

    elif token_class is TokenClass.BUDGET:
        triggers |= TriggerFlag.TOKEN_BUDGET
        regime = Regime.STOP

    elif phase is Phase.START:
        if token_class is TokenClass.WHITESPACE:
            pass
        elif token_class is TokenClass.OPEN_BRACE:
            phase = Phase.JSON
            regime = Regime.JSON_ACTION
            depth = 1
            constraints |= ConstraintFlag.JSON_STARTED
            triggers |= TriggerFlag.JSON_OPENED
            residence = 0
        else:
            phase = Phase.INVALID
            regime = Regime.RECOVERY
            triggers |= TriggerFlag.INVALID_PREFIX
            residence = 0

    elif phase is Phase.JSON:
        if token_class is TokenClass.QUOTE:
            phase = Phase.STRING
            constraints |= ConstraintFlag.IN_STRING
        elif token_class is TokenClass.OPEN_BRACE:
            if depth >= MAX_JSON_DEPTH:
                phase = Phase.INVALID
                regime = Regime.RECOVERY
                triggers |= TriggerFlag.DEPTH_OVERFLOW
            else:
                depth += 1
        elif token_class is TokenClass.CLOSE_BRACE:
            if depth == 0:
                phase = Phase.INVALID
                regime = Regime.RECOVERY
                triggers |= TriggerFlag.INVALID_PREFIX
            else:
                depth -= 1
                if depth == 0:
                    phase = Phase.COMPLETE
                    regime = Regime.STOP
                    constraints |= ConstraintFlag.JSON_COMPLETE
                    triggers |= TriggerFlag.JSON_CLOSED
                    residence = 0

    elif phase is Phase.STRING:
        if token_class is TokenClass.BACKSLASH:
            phase = Phase.ESCAPE
            constraints |= ConstraintFlag.ESCAPE_PENDING
        elif token_class is TokenClass.QUOTE:
            phase = Phase.JSON
            constraints &= ~ConstraintFlag.IN_STRING

    elif phase is Phase.ESCAPE:
        phase = Phase.STRING
        constraints &= ~ConstraintFlag.ESCAPE_PENDING

    return MarkovHeader(
        version=header.version,
        regime=int(regime),
        phase=int(phase),
        residual_slot=header.residual_slot,
        gain_q15=header.gain_q15,
        constraint_flags=int(constraints),
        trigger_flags=int(triggers),
        residence=residence,
        json_depth=depth,
        token_class=int(token_class),
        sequence=(header.sequence + 1) & 0xFFFF,
    )


def classify_character(character: str) -> TokenClass:
    if len(character) != 1:
        raise ValueError("classify_character requires exactly one character")
    if character.isspace():
        return TokenClass.WHITESPACE
    if character == "{":
        return TokenClass.OPEN_BRACE
    if character == "}":
        return TokenClass.CLOSE_BRACE
    if character == '"':
        return TokenClass.QUOTE
    if character == "\\":
        return TokenClass.BACKSLASH
    return TokenClass.OTHER


def apply_token_text(header: MarkovHeader, token_text: str) -> MarkovHeader:
    """Reference token-text application outside the production hot path."""
    current = header
    for character in token_text:
        current = transition(current, classify_character(character))
        if current.regime == int(Regime.STOP) or current.phase == int(Phase.INVALID):
            break
    return current


def compose_token_texts(header: MarkovHeader, token_texts: Iterable[str]) -> MarkovHeader:
    current = header
    for token_text in token_texts:
        current = apply_token_text(current, token_text)
        if current.regime == int(Regime.STOP) or current.phase == int(Phase.INVALID):
            break
    return current


def terminal_trigger(header: MarkovHeader) -> TriggerFlag:
    return TriggerFlag(header.trigger_flags) & (
        TriggerFlag.JSON_CLOSED
        | TriggerFlag.INVALID_PREFIX
        | TriggerFlag.EOS
        | TriggerFlag.REPETITION
        | TriggerFlag.TOKEN_BUDGET
        | TriggerFlag.DEPTH_OVERFLOW
    )
