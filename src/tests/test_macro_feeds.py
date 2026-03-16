from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from src.macro.adapters import (
    AlphaVantageAdapter,
    COMEXOpenInterestAdapter,
    CentralBankReserveAdapter,
    EconomicCalendarAdapter,
    FREDAdapter,
    GoldEtfFlowsAdapter,
    GoldOptionMagnetAdapter,
    GoldPhysicalPremiumAdapter,
    TreasuryYieldsAdapter,
)
from src.macro.gold_macro import (
    CORRELATION_BREAK_CONFIDENCE_PENALTY,
    CORRELATION_BREAK_SIZE_MULTIPLIER,
    MacroFeedConfig,
    collect_xauusd_macro_state,
)


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
        fetcher=lambda _url: [
            {
                "impact": "High",
                "event": "US CPI",
                "datetime": (datetime.now(tz=timezone.utc) + timedelta(minutes=20)).isoformat(),
            },
            {"impact": "Medium", "event": "Retail Sales"},
        ],
    ).fetch_events()
    assert calendar["available"] is True
    assert calendar["state"] == "elevated"
    assert calendar["metrics"]["high_impact_count"] == 1
    assert calendar["metrics"]["upcoming_major_events_60m"] >= 1
    assert calendar["metrics"]["event_type"] == "major_macro_release"


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
    assert latest_payload["feed_states"]["comex_open_interest"]["available"] is False
    assert latest_payload["feed_states"]["gold_etf_flows"]["available"] is False
    assert latest_payload["feed_states"]["gold_option_magnet_levels"]["available"] is False
    assert latest_payload["feed_states"]["gold_physical_premium_discount"]["available"] is False
    assert latest_payload["feed_states"]["central_bank_gold_reserves"]["available"] is False
    assert macro["trade_tags"]["macro_state"] in {"risk_off", "balanced"}
    assert macro["trade_tags"]["correlation_regime_state"] in {
        "insufficient_data",
        "correlation_stable",
        "correlation_break_detected",
    }
    assert macro["session_policy"]["state"] in {
        "asia_reduced_size",
        "london_normal_size",
        "new_york_moderate_size",
        "normal_size",
    }


def test_external_gold_feed_stubs_mark_unavailable_when_endpoint_missing() -> None:
    assert COMEXOpenInterestAdapter().fetch_state()["available"] is False
    assert GoldEtfFlowsAdapter().fetch_state()["available"] is False
    assert GoldOptionMagnetAdapter().fetch_state()["available"] is False
    assert GoldPhysicalPremiumAdapter().fetch_state()["available"] is False
    assert CentralBankReserveAdapter().fetch_state()["available"] is False


def test_friday_policy_and_major_round_number_risk_are_enforced(tmp_path: Path) -> None:
    friday = datetime(2026, 3, 13, 17, 0, tzinfo=timezone.utc)
    bars = [
        {"time": int((friday - timedelta(minutes=5)).timestamp()), "close": 1900.1},
        {"time": int(friday.timestamp()), "close": 1900.3},
    ]
    macro = collect_xauusd_macro_state(
        memory_root=str(tmp_path / "memory"),
        bars=bars,
        session_state="london",
        volatility_regime="compression",
        config=MacroFeedConfig(
            alpha_vantage_api_key="",
            fred_api_key="",
            treasury_endpoint="https://example.com/treasury",
            economic_calendar_endpoint="https://example.com/calendar",
            enabled=False,
        ),
    )
    assert macro["risk_behavior"]["pause_trading"] is True
    assert "friday_afternoon_trading_disabled" in macro["risk_behavior"]["reasons"]
    assert macro["major_round_number"]["state"] == "near_major_round_number"


def test_correlation_regime_break_detector_reduces_size_and_confidence(tmp_path: Path, monkeypatch) -> None:
    dxy_sequence = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
    us10y_sequence = [0.04, 0.08, 0.12, 0.16, 0.20, 0.24]
    state = {"idx": 0}

    def _mock_alpha(_self) -> dict[str, object]:
        idx = min(state["idx"], len(dxy_sequence) - 1)
        return {
            "feed": "alpha_vantage",
            "available": True,
            "stale": False,
            "state": "neutral_usd",
            "reason_codes": [],
            "metrics": {"usd_proxy_change": dxy_sequence[idx]},
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    def _mock_fred(_self) -> dict[str, dict[str, object]]:
        idx = min(state["idx"], len(us10y_sequence) - 1)
        return {
            "DGS10": {
                "available": True,
                "stale": False,
                "value": 4.0,
                "previous_value": 3.8,
                "change": us10y_sequence[idx],
                "reason_codes": [],
            },
            "DGS2": {
                "available": True,
                "stale": False,
                "value": 3.8,
                "previous_value": 3.7,
                "change": 0.02,
                "reason_codes": [],
            },
            "T10YIE": {
                "available": True,
                "stale": False,
                "value": 2.0,
                "previous_value": 2.0,
                "change": 0.0,
                "reason_codes": [],
            },
            "REAL_RATE_PROXY": {
                "available": True,
                "stale": False,
                "value": 2.0,
                "previous_value": None,
                "change": None,
                "reason_codes": [],
            },
        }

    monkeypatch.setattr("src.macro.gold_macro.AlphaVantageAdapter.fetch_dxy_proxy", _mock_alpha)
    monkeypatch.setattr("src.macro.gold_macro.FREDAdapter.fetch_core_macro", _mock_fred)
    monkeypatch.setattr(
        "src.macro.gold_macro.TreasuryYieldsAdapter.fetch_yields",
        lambda _self: {
            "feed": "treasury",
            "available": True,
            "stale": False,
            "state": "available",
            "reason_codes": [],
            "metrics": {"yield_10y": 4.0, "yield_2y": 3.8, "curve_10y_2y": 0.2},
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        },
    )
    monkeypatch.setattr(
        "src.macro.gold_macro.EconomicCalendarAdapter.fetch_events",
        lambda _self: {
            "feed": "economic_calendar",
            "available": True,
            "stale": False,
            "state": "calm",
            "reason_codes": [],
            "metrics": {
                "high_impact_count": 0,
                "major_event_count": 0,
                "event_count": 0,
                "upcoming_major_events_60m": 0,
                "recent_major_events_30m": 0,
                "event_type": "routine_calendar",
            },
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        },
    )

    last_macro: dict[str, object] = {}
    break_macro: dict[str, object] | None = None
    for idx in range(1, 7):
        state["idx"] = idx - 1
        bars = [
            {"time": 4_100_000_000 + idx * 60 - 60, "close": 2000.0},
            {"time": 4_100_000_000 + idx * 60, "close": 2000.0 + (idx * 0.25)},
        ]
        last_macro = collect_xauusd_macro_state(
            memory_root=str(tmp_path / "memory_corr"),
            bars=bars,
            session_state="new_york",
            volatility_regime="balanced",
            config=MacroFeedConfig(
                alpha_vantage_api_key="key",
                fred_api_key="key",
                treasury_endpoint="https://example.com/treasury",
                economic_calendar_endpoint="https://example.com/calendar",
                enabled=True,
            ),
        )
        if bool(last_macro["correlation_regime"]["break_detected"]):
            break_macro = dict(last_macro)

    assert break_macro is not None
    assert break_macro["trade_tags"]["correlation_regime_state"] == "correlation_break_detected"
    assert "correlation_regime_break_detected" in break_macro["risk_behavior"]["reasons"]
    assert break_macro["risk_behavior"]["size_multiplier"] <= CORRELATION_BREAK_SIZE_MULTIPLIER
    assert break_macro["risk_behavior"]["confidence_penalty"] >= CORRELATION_BREAK_CONFIDENCE_PENALTY
    assert Path(last_macro["correlation_regime"]["paths"]["state"]).exists()
    assert Path(last_macro["correlation_regime"]["paths"]["history"]).exists()
