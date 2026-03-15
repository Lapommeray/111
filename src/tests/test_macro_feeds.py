from __future__ import annotations

import json
from pathlib import Path

from src.macro.adapters import AlphaVantageAdapter, EconomicCalendarAdapter, FREDAdapter, TreasuryYieldsAdapter
from src.macro.gold_macro import MacroFeedConfig, collect_xauusd_macro_state


def test_alpha_vantage_adapter_parses_usd_proxy_state() -> None:
    def _fetcher(_url: str) -> dict[str, object]:
        return {
            "Time Series FX (Daily)": {
                "2026-03-14": {"4. close": "1.0800"},
                "2026-03-13": {"4. close": "1.0900"},
            }
        }

    state = AlphaVantageAdapter(api_key="key", fetcher=_fetcher).fetch_dxy_proxy()
    assert state["available"] is True
    assert state["state"] == "strong_usd"
    assert state["metrics"]["usd_proxy_change"] > 0


def test_fred_adapter_and_treasury_calendar_adapters_parse_payloads() -> None:
    def _fred_fetcher(url: str) -> dict[str, object]:
        if "DGS10" in url:
            value = "4.20"
        elif "DGS2" in url:
            value = "4.10"
        else:
            value = "2.10"
        return {"observations": [{"date": "2026-03-14", "value": value}, {"date": "2026-03-13", "value": value}]}

    fred = FREDAdapter(api_key="key", fetcher=_fred_fetcher).fetch_core_macro()
    assert fred["DGS10"]["available"] is True
    assert fred["DGS2"]["available"] is True
    assert fred["T10YIE"]["available"] is True
    assert fred["REAL_RATE_PROXY"]["value"] == 2.1

    treasury = TreasuryYieldsAdapter(
        endpoint="https://example.com/treasury",
        fetcher=lambda _url: {"data": {"10Y": "4.20", "2Y": "4.00"}},
    ).fetch_yields()
    assert treasury["available"] is True
    assert treasury["metrics"]["curve_10y_2y"] == 0.2

    calendar = EconomicCalendarAdapter(
        endpoint="https://example.com/calendar",
        fetcher=lambda _url: [{"impact": "High", "event": "US CPI"}, {"impact": "Medium", "event": "Retail Sales"}],
    ).fetch_events()
    assert calendar["available"] is True
    assert calendar["state"] == "elevated"
    assert calendar["metrics"]["high_impact_count"] == 1


def test_collect_xauusd_macro_state_logs_unavailable_feeds_and_tags(tmp_path: Path) -> None:
    bars = [
        {"time": 4_000_000_000 - 60, "close": 2010.0},
        {"time": 4_000_000_000, "close": 2010.2},
    ]
    macro = collect_xauusd_macro_state(
        memory_root=str(tmp_path / "memory"),
        bars=bars,
        session_state="new_york",
        volatility_regime="expansion",
        config=MacroFeedConfig(
            alpha_vantage_api_key="",
            fred_api_key="",
            treasury_endpoint="https://example.com/treasury",
            economic_calendar_endpoint="https://example.com/calendar",
            enabled=False,
        ),
    )
    assert macro["macro_states"]["dxy_state"] == "unavailable"
    assert macro["risk_behavior"]["confidence_penalty"] > 0
    assert macro["trade_tags"]["session"] == "new_york"
    assert macro["trade_tags"]["volatility_regime"] == "expansion"
    assert macro["trade_tags"]["round_number_proximity"] in {
        "near_round_number",
        "approaching_round_number",
        "clear_round_number",
    }
    latest_path = Path(macro["paths"]["latest"])
    history_path = Path(macro["paths"]["history"])
    assert latest_path.exists()
    assert history_path.exists()
    latest_payload = json.loads(latest_path.read_text(encoding="utf-8"))
    assert "feed_states" in latest_payload
    assert latest_payload["feed_states"]["alpha_vantage"]["available"] is False
