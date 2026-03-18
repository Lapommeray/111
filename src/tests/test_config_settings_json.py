from __future__ import annotations

import json
from pathlib import Path


def test_settings_json_is_valid_and_has_required_keys() -> None:
    settings_path = Path(__file__).resolve().parents[2] / "config" / "settings.json"
    payload = json.loads(settings_path.read_text(encoding="utf-8"))

    for key in (
        "symbol",
        "timeframe",
        "bars",
        "sample_path",
        "memory_root",
        "evaluation_output_path",
        "walk_forward_enabled",
        "walk_forward_context_bars",
        "walk_forward_test_bars",
        "walk_forward_step_bars",
        "execution_spread_cost_points",
        "execution_commission_cost_points",
        "execution_slippage_cost_points",
        "knowledge_candidate_limit",
    ):
        assert key in payload
