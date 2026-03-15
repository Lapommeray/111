from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class CandidateModuleFactory:
    """Builds inspectable module specifications from hypotheses only."""

    def generate(self, hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        specs: list[dict[str, Any]] = []
        for hypothesis in hypotheses:
            hid = str(hypothesis.get("hypothesis_id", "unknown"))
            truth_class = str(hypothesis.get("truth_class", "meta-intelligence"))
            statement = str(hypothesis.get("statement", "")).strip()
            created_at = datetime.now(tz=timezone.utc).isoformat()
            specs.append(
                {
                    "candidate_id": f"cand_{hid}",
                    "hypothesis_id": hid,
                    "truth_class": truth_class,
                    "module_kind": self._module_kind_for_truth_class(truth_class),
                    "candidate_name": self._name_from_statement(truth_class, statement),
                    "spec": {
                        "purpose": statement,
                        "inputs": ["advanced_modules", "signal", "status_panel"],
                        "outputs": ["direction_vote", "confidence_delta", "reasons", "payload"],
                        "constraints": [
                            "xauusd_first_only",
                            "no_core_strategy_mutation",
                            "json_friendly_artifact_only",
                        ],
                    },
                    "created_at": created_at,
                }
            )
        return specs

    def _module_kind_for_truth_class(self, truth_class: str) -> str:
        mapping = {
            "regime": "regime_classifier",
            "participation": "participation_feature",
            "liquidity": "liquidity_feature",
            "timing": "timing_filter",
            "failure": "failure_filter",
            "meta-intelligence": "diagnostic_module",
        }
        return mapping.get(truth_class, "diagnostic_module")

    def _name_from_statement(self, truth_class: str, statement: str) -> str:
        tokens = [t.lower() for t in statement.replace("_", " ").split() if t.isalpha()]
        core = "_".join(tokens[:4]) if tokens else "candidate"
        return f"{truth_class}_{core}"[:64]
