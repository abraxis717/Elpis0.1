from __future__ import annotations

from elpis_nanbeige42_host.markov_trigger_header import (
    HEADER_BYTES,
    ConstraintFlag,
    MarkovHeader,
    Phase,
    Regime,
    TokenClass,
    TriggerFlag,
    apply_token_text,
    compose_token_texts,
    terminal_trigger,
    transition,
)


def test_header_is_exactly_sixteen_bytes_and_round_trips() -> None:
    header = MarkovHeader(residual_slot=7, gain_q15=1234, sequence=9)
    packed = header.pack()
    assert len(packed) == HEADER_BYTES == 16
    assert MarkovHeader.unpack(packed) == header


def test_leading_whitespace_is_allowed_before_bare_json() -> None:
    header = apply_token_text(MarkovHeader(), " \n\t{")
    assert header.phase == int(Phase.JSON)
    assert header.json_depth == 1
    assert TriggerFlag.JSON_OPENED & TriggerFlag(header.trigger_flags)


def test_first_non_whitespace_prose_triggers_invalid_prefix() -> None:
    header = apply_token_text(MarkovHeader(), "\nVERIFICATION")
    assert header.phase == int(Phase.INVALID)
    assert header.regime == int(Regime.RECOVERY)
    assert TriggerFlag.INVALID_PREFIX & TriggerFlag(header.trigger_flags)
    assert terminal_trigger(header)


def test_complete_json_triggers_stop() -> None:
    header = apply_token_text(
        MarkovHeader(),
        '{"schema":"elpis.nanbeige42.coding-action.v1","action":"report_blocker","reason":"x"}',
    )
    assert header.phase == int(Phase.COMPLETE)
    assert header.regime == int(Regime.STOP)
    assert header.json_depth == 0
    assert ConstraintFlag.JSON_COMPLETE & ConstraintFlag(header.constraint_flags)
    assert TriggerFlag.JSON_CLOSED & TriggerFlag(header.trigger_flags)


def test_braces_inside_string_do_not_change_depth() -> None:
    header = apply_token_text(MarkovHeader(), '{"content":"{x}"}')
    assert header.phase == int(Phase.COMPLETE)
    assert header.json_depth == 0


def test_escaped_quote_does_not_close_string() -> None:
    header = apply_token_text(MarkovHeader(), '{"content":"a\\\"b"}')
    assert header.phase == int(Phase.COMPLETE)
    assert header.json_depth == 0


def test_eos_before_json_completion_is_terminal_failure() -> None:
    header = apply_token_text(MarkovHeader(), '{"x":')
    header = transition(header, TokenClass.EOS)
    flags = TriggerFlag(header.trigger_flags)
    assert TriggerFlag.EOS & flags
    assert TriggerFlag.INCOMPLETE_EOS & flags
    assert header.regime == int(Regime.STOP)


def test_repetition_is_trigger_not_inline_repair() -> None:
    header = transition(MarkovHeader(), TokenClass.REPETITION)
    assert header.regime == int(Regime.RECOVERY)
    assert TriggerFlag.REPETITION & TriggerFlag(header.trigger_flags)


def test_budget_is_terminal_trigger() -> None:
    header = transition(MarkovHeader(), TokenClass.BUDGET)
    assert header.regime == int(Regime.STOP)
    assert TriggerFlag.TOKEN_BUDGET & TriggerFlag(header.trigger_flags)


def test_token_effect_composition_matches_concatenation() -> None:
    initial = MarkovHeader()
    left = compose_token_texts(initial, ['{"a"', ':', '"b"}'])
    right = apply_token_text(initial, '{"a":"b"}')
    assert left == right


def test_empty_token_text_is_identity() -> None:
    header = MarkovHeader(residual_slot=3, gain_q15=111)
    assert apply_token_text(header, "") == header


def test_stopped_header_does_not_reopen() -> None:
    complete = apply_token_text(MarkovHeader(), "{}")
    after = transition(complete, TokenClass.OPEN_BRACE)
    assert after.regime == int(Regime.STOP)
    assert after.phase == int(Phase.COMPLETE)
