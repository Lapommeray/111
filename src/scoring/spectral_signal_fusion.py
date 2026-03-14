from __future__ import annotations

from typing import Any


def fuse_spectral_signals(module_outputs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Combines existing module outputs into a transparent fused contribution."""
    selected = [
        module_outputs.get("displacement", {}),
        module_outputs.get("fvg", {}),
        module_outputs.get("volatility", {}),
        module_outputs.get("quantum_tremor_scanner", {}),
        module_outputs.get("invisible_data_miner", {}),
        module_outputs.get("human_lag_exploit", {}),
    ]

    deltas = [float(x.get("confidence_delta", 0.0)) for x in selected]
    avg_delta = sum(deltas) / len(deltas) if deltas else 0.0

    votes = [str(x.get("direction_vote", "neutral")).lower() for x in selected]
    buy_votes = sum(1 for v in votes if v == "buy")
    sell_votes = sum(1 for v in votes if v == "sell")

    if buy_votes > sell_votes:
        vote = "buy"
    elif sell_votes > buy_votes:
        vote = "sell"
    else:
        vote = "neutral"

    return {
        "module": "spectral_signal_fusion",
        "state": "computed",
        "direction_vote": vote,
        "confidence_delta": round(avg_delta, 4),
        "reasons": [f"buy_votes={buy_votes}", f"sell_votes={sell_votes}", f"avg_delta={round(avg_delta,4)}"],
    }
