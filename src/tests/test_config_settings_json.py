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
        "knowledge_candidate_limit",
    ):
        assert key in payload
