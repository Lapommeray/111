from __future__ import annotations

from typing import Any


def compute_setup_score(module_outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Summarize setup quality without re-applying confidence deltas.

    This module is intentionally informational: it produces a normalized setup
    score and traceability details, while leaving final confidence aggregation to
    the pipeline-wide delta combiner.
    """
    confidence_inputs: list[float] = []
    contributing_modules: list[str] = []

    for name, output in module_outputs.items():
        delta = float(output.get("confidence_delta", 0.0))
        if delta != 0.0:
            confidence_inputs.append(delta)
            contributing_modules.append(name)

    if confidence_inputs:
        avg_delta = sum(confidence_inputs) / len(confidence_inputs)
    else:
        avg_delta = 0.0

    score = max(0.0, min(1.0, round(0.5 + avg_delta, 4)))

    return {
        "module": "setup_score",
        "score": score,
        "confidence_delta": 0.0,
        "input_avg_delta": round(avg_delta, 4),
        "input_count": len(confidence_inputs),
        "contributing_modules": contributing_modules,
        "reasons": [
            "informational_setup_score",
            f"input_count={len(confidence_inputs)}",
            f"input_avg_delta={round(avg_delta, 4)}",
        ],
    }
