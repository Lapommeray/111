from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils import read_json_safe, write_json_atomic


class HypothesisRegistry:
    """JSON-backed registry for autonomous knowledge hypotheses."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            write_json_atomic(self.path, {"hypotheses": []})

    def load(self) -> dict[str, Any]:
        data = read_json_safe(self.path, default={"hypotheses": []})
        if not isinstance(data, dict):
            return {"hypotheses": []}
        hypotheses = data.get("hypotheses", [])
        if not isinstance(hypotheses, list):
            return {"hypotheses": []}
        return {"hypotheses": hypotheses}

    def register(self, hypothesis: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(tz=timezone.utc).isoformat()
        payload = self.load()
        entry = {
            "hypothesis_id": hypothesis.get(
                "hypothesis_id",
                f"hyp_{datetime.now(tz=timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
            ),
            "created_at": now,
            "truth_class": str(hypothesis.get("truth_class", "meta-intelligence")),
            "truth_class_rationale": str(hypothesis.get("truth_class_rationale", "")),
            "usefulness_scope": str(hypothesis.get("usefulness_scope", "general")),
            "statement": str(hypothesis.get("statement", "")),
            "evidence": hypothesis.get("evidence", {}),
            "source": str(hypothesis.get("source", "replay_evaluation")),
            "status": str(hypothesis.get("status", "candidate")),
        }
        payload["hypotheses"].append(entry)
        write_json_atomic(self.path, payload)
        return entry
