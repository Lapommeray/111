from __future__ import annotations

from run import _should_apply_replay_wait_structure_override


def test_replay_wait_override_is_guarded_for_soft_conflict_low_effective_confidence() -> None:
    apply_override, reason = _should_apply_replay_wait_structure_override(
        decision="WAIT",
        structure_bias="sell",
        advanced_confidence=0.62,
        hard_liquidity_conflict=False,
        memory_root="memory/__replay_isolation",
        combined_reasons=["structure_liquidity_conflict_soft"],
        effective_signal_confidence=0.41,
    )
    assert apply_override is False
    assert reason == "replay_drawdown_soft_conflict_override_guard"


def test_replay_wait_override_still_applies_without_soft_conflict_guard_condition() -> None:
    apply_override, reason = _should_apply_replay_wait_structure_override(
        decision="WAIT",
        structure_bias="buy",
        advanced_confidence=0.62,
        hard_liquidity_conflict=False,
        memory_root="memory/__replay_isolation",
        combined_reasons=["advanced_direction=WAIT"],
        effective_signal_confidence=0.41,
    )
    assert apply_override is True
    assert reason == ""
