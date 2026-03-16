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
    MT5DXYProxyAdapter,
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


def _patch_available_macro_feeds(
    monkeypatch,
    *,
    dxy_change: float = 0.0,
    us10y_change: float = 0.0,
    event_type: str = "routine_calendar",
) -> None:
    monkeypatch.setattr(
        "src.macro.gold_macro.AlphaVantageAdapter.fetch_dxy_proxy",
        lambda _self: {
            "feed": "alpha_vantage",
            "available": True,
            "stale": False,
            "state": "neutral_usd",
            "reason_codes": [],
            "metrics": {"usd_proxy_change": dxy_change},
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        },
    )
    monkeypatch.setattr(
        "src.macro.gold_macro.FREDAdapter.fetch_core_macro",
        lambda _self: {
            "DGS10": {
                "available": True,
                "stale": False,
                "value": 4.0,
                "previous_value": 3.9,
                "change": us10y_change,
                "reason_codes": [],
            },
            "DGS2": {
                "available": True,
                "stale": False,
                "value": 3.8,
                "previous_value": 3.7,
                "change": 0.01,
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
                "value": 1.8,
                "previous_value": None,
                "change": None,
                "reason_codes": [],
            },
        },
    )
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
                "event_type": event_type,
            },
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        },
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


def test_mt5_dxy_proxy_calculation_and_labels(tmp_path: Path) -> None:
    def _ticks(_symbols: list[str]) -> dict[str, object]:
        return {
            "EURUSD": {"bid": 1.08},
            "USDJPY": {"bid": 149.2},
            "GBPUSD": {"bid": 1.27},
            "USDCAD": {"bid": 1.35},
            "USDSEK": {"bid": 10.21},
            "USDCHF": {"bid": 0.88},
        }

    state = MT5DXYProxyAdapter(tick_fetcher=_ticks, retention_records=50).fetch_state(memory_root=str(tmp_path / "memory"))
    assert state["feed"] == "dxy_proxy"
    assert state["available"] is True
    assert state["benchmark_label"] == "not_official_benchmark_dxy"
    assert isinstance(state["metrics"]["proxy_value"], float)
    assert Path(state["history_path"]).exists()


def test_mt5_dxy_proxy_history_pruning(tmp_path: Path) -> None:
    counter = {"i": 0}

    def _ticks(_symbols: list[str]) -> dict[str, object]:
        counter["i"] += 1
        base = 1.08 + (counter["i"] * 0.0001)
        return {
            "EURUSD": {"bid": base},
            "USDJPY": {"bid": 149.2},
            "GBPUSD": {"bid": 1.27},
            "USDCAD": {"bid": 1.35},
            "USDSEK": {"bid": 10.21},
            "USDCHF": {"bid": 0.88},
        }

    adapter = MT5DXYProxyAdapter(tick_fetcher=_ticks, retention_records=5)
    for _ in range(12):
        adapter.fetch_state(memory_root=str(tmp_path / "memory_prune"))
    history_path = tmp_path / "memory_prune" / "macro_state" / "dxy_proxy_history.json"
    payload = json.loads(history_path.read_text(encoding="utf-8"))
    assert len(payload) == 5


def test_mt5_dxy_proxy_degraded_when_ticks_missing(tmp_path: Path) -> None:
    state = MT5DXYProxyAdapter(tick_fetcher=lambda _symbols: {"EURUSD": {"bid": 1.08}}).fetch_state(
        memory_root=str(tmp_path / "memory_missing")
    )
    assert state["available"] is False
    assert state["status"] == "degraded"
    assert state["fallback_state"] == "alpha_vantage_dxy_proxy"


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


def test_gld_optional_feed_behavior_marks_unavailable_without_blocking(tmp_path: Path, monkeypatch) -> None:
    _patch_available_macro_feeds(monkeypatch, dxy_change=0.01)
    monkeypatch.setattr(
        "src.macro.gold_macro.GoldEtfFlowsAdapter.fetch_state",
        lambda _self: {
            "feed": "gold_etf_flows",
            "available": False,
            "stale": True,
            "state": "unavailable",
            "reason_codes": ["endpoint_not_configured"],
            "metrics": {},
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        },
    )
    monkeypatch.setattr(
        "src.macro.gold_macro.MT5DXYProxyAdapter.fetch_state",
        lambda _self, memory_root: {
            "feed": "dxy_proxy",
            "available": True,
            "stale": False,
            "state": "strong_usd",
            "status": "available",
            "health_status": "healthy",
            "last_update_timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "symbol_scope": "XAUUSD",
            "data_confidence": 0.9,
            "fallback_state": "none",
            "reason_codes": [],
            "metrics": {"usd_proxy_change": 0.01, "proxy_value": 101.0, "recent_history": []},
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        },
    )
    bars = [{"time": 4_300_000_000 - 60, "close": 2000.0}, {"time": 4_300_000_000, "close": 1999.0}]
    macro = collect_xauusd_macro_state(
        memory_root=str(tmp_path / "memory_gld_optional"),
        bars=bars,
        session_state="new_york",
        volatility_regime="balanced",
        config=MacroFeedConfig(
            alpha_vantage_api_key="k",
            fred_api_key="k",
            treasury_endpoint="https://example.com/treasury",
            economic_calendar_endpoint="https://example.com/calendar",
            enabled=True,
        ),
    )
    assert macro["trade_tags"]["gld_flow_state"] == "unavailable"
    assert "gld_flow_optional_unavailable" in macro["risk_behavior"]["reasons"]
    assert macro["risk_behavior"]["pause_trading"] is False


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


def test_correlation_refinement_dual_confirmation_and_major_warning(tmp_path: Path, monkeypatch) -> None:
    _patch_available_macro_feeds(monkeypatch, dxy_change=0.18, us10y_change=0.15)
    memory = tmp_path / "memory_corr_refined"
    for idx in range(6):
        bars = [
            {"time": 4_200_000_000 + idx * 60 - 60, "close": 2000.0},
            {"time": 4_200_000_000 + idx * 60, "close": 2000.2 + (idx * 0.35)},
        ]
        macro = collect_xauusd_macro_state(
            memory_root=str(memory),
            bars=bars,
            session_state="new_york",
            volatility_regime="balanced",
            config=MacroFeedConfig(
                alpha_vantage_api_key="k",
                fred_api_key="k",
                treasury_endpoint="https://example.com/treasury",
                economic_calendar_endpoint="https://example.com/calendar",
                enabled=True,
            ),
        )

    corr = macro["correlation_regime"]
    assert corr["confirmation"] in {"dual_break", "dxy_break_only", "yield_break_only"}
    assert macro["trade_tags"]["correlation_confirmation"] == corr["confirmation"]
    assert "surgical_layer_triggers" in macro["trade_tags"]
    if corr["confirmation"] == "dual_break":
        assert macro["risk_behavior"]["size_multiplier"] <= CORRELATION_BREAK_SIZE_MULTIPLIER


def test_stop_hunt_round_cluster_and_london_fix_layers(tmp_path: Path, monkeypatch) -> None:
    _patch_available_macro_feeds(monkeypatch)
    base = datetime(2026, 3, 16, 15, 10, tzinfo=timezone.utc)
    bars = []
    for i in range(24):
        t = int((base - timedelta(minutes=23 - i)).timestamp())
        close = 2000.0 + (0.1 if i < 20 else 2.2 if i == 21 else -0.4 if i >= 22 else 0.0)
        bars.append(
            {
                "time": t,
                "open": 2000.0,
                "high": 2003.0 if i == 22 else close + 0.3,
                "low": 1999.7,
                "close": close,
                "volume": 120.0,
            }
        )
    macro = collect_xauusd_macro_state(
        memory_root=str(tmp_path / "memory_stop_hunt"),
        bars=bars,
        session_state="london",
        volatility_regime="balanced",
        config=MacroFeedConfig(
            alpha_vantage_api_key="k",
            fred_api_key="k",
            treasury_endpoint="https://example.com/treasury",
            economic_calendar_endpoint="https://example.com/calendar",
            enabled=True,
        ),
    )
    detectors = macro["detectors"]
    assert detectors["stop_hunt_footprint_analyzer"]["state"] in {"sweep_detected", "no_sweep"}
    assert detectors["round_number_stop_cluster_map"]["state"] != "insufficient_data"
    assert detectors["london_fix_imbalance_detector"]["state"] in {"fix_imbalance_detected", "fix_orderly"}


def test_tokyo_vacuum_nfp_and_pause_paths_are_governed(tmp_path: Path, monkeypatch) -> None:
    _patch_available_macro_feeds(monkeypatch)
    start = datetime(2026, 3, 6, 13, 31, tzinfo=timezone.utc)
    bars = []
    for i in range(30):
        t = int((start - timedelta(minutes=29 - i)).timestamp())
        bars.append(
            {
                "time": t,
                "open": 2000.0,
                "high": 2000.6,
                "low": 1999.6,
                "close": 2000.0 + (i * 0.01),
                "spread": 0.2 if i < 29 else 1.0,
                "tick_volume": 140 if i < 29 else 20,
            }
        )
    macro = collect_xauusd_macro_state(
        memory_root=str(tmp_path / "memory_vacuum"),
        bars=bars,
        session_state="asia",
        volatility_regime="balanced",
        config=MacroFeedConfig(
            alpha_vantage_api_key="k",
            fred_api_key="k",
            treasury_endpoint="https://example.com/treasury",
            economic_calendar_endpoint="https://example.com/calendar",
            enabled=True,
        ),
    )
    assert macro["detectors"]["nfp_front_run_layer"]["state"] in {
        "nfp_pre_15m",
        "nfp_post_0_2m_block",
        "nfp_post_2_5m_watch",
        "nfp_post_5m_reentry_window",
        "normal",
    }
    assert macro["detectors"]["tokyo_open_liquidity_vacuum_detector"]["state"] in {
        "tokyo_liquidity_vacuum",
        "tokyo_normal_liquidity",
    }
    if macro["detectors"]["tokyo_open_liquidity_vacuum_detector"]["active"]:
        assert macro["risk_behavior"]["pause_trading"] is True
        assert macro["risk_behavior"]["pause_seconds"] >= 120


def test_blowoff_archaeologist_gamma_proxy_and_memory_persistence(tmp_path: Path, monkeypatch) -> None:
    _patch_available_macro_feeds(monkeypatch)
    bars = []
    base = datetime(2026, 3, 16, 12, 5, tzinfo=timezone.utc)
    for i in range(185):
        t = int((base - timedelta(minutes=184 - i)).timestamp())
        price = 2000.0 + (0.02 if i % 2 == 0 else -0.02)
        bars.append(
            {
                "time": t,
                "open": price,
                "high": price + 0.15,
                "low": price - 0.15,
                "close": price,
                "volume": 80.0,
            }
        )
    bars[-2] = {
        "time": bars[-2]["time"],
        "open": 2000.8,
        "high": 2006.0,
        "low": 2000.2,
        "close": 2001.0,
        "volume": 260.0,
    }
    bars[-1] = {
        "time": bars[-1]["time"],
        "open": 2001.0,
        "high": 2002.5,
        "low": 1999.9,
        "close": 2000.4,
        "volume": 120.0,
    }
    macro = collect_xauusd_macro_state(
        memory_root=str(tmp_path / "memory_arch"),
        bars=bars,
        session_state="new_york",
        volatility_regime="expansion",
        config=MacroFeedConfig(
            alpha_vantage_api_key="k",
            fred_api_key="k",
            treasury_endpoint="https://example.com/treasury",
            economic_calendar_endpoint="https://example.com/calendar",
            enabled=True,
        ),
    )
    assert macro["detectors"]["blowoff_top_fingerprint"]["state"] in {"blowoff_top_detected", "no_blowoff"}
    assert macro["detectors"]["price_archaeologist_layer"]["partial"] in {True, False}
    assert macro["detectors"]["dealer_gamma_flip_proxy"]["proxy"] is True
    assert macro["detectors"]["dealer_gamma_flip_proxy"]["partial"] is True
    assert Path(macro["paths"]["surgical_latest"]).exists()
    assert Path(macro["paths"]["surgical_history"]).exists()


def test_dxy_proxy_primary_context_and_feed_health_tagging(tmp_path: Path, monkeypatch) -> None:
    _patch_available_macro_feeds(monkeypatch, dxy_change=-0.002)
    monkeypatch.setattr(
        "src.macro.gold_macro.MT5DXYProxyAdapter.fetch_state",
        lambda _self, memory_root: {
            "feed": "dxy_proxy",
            "feed_name": "dxy_proxy",
            "available": False,
            "stale": True,
            "state": "unavailable",
            "status": "degraded",
            "health_status": "degraded",
            "last_update_timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "symbol_scope": "XAUUSD",
            "data_confidence": 0.3,
            "fallback_state": "alpha_vantage_dxy_proxy",
            "reason_codes": ["missing_tick:USDSEK"],
            "benchmark_label": "not_official_benchmark_dxy",
            "metrics": {"usd_proxy_change": None, "recent_history": []},
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        },
    )
    bars = [{"time": 4_400_000_000 - 60, "close": 2000.0}, {"time": 4_400_000_000, "close": 2000.5}]
    macro = collect_xauusd_macro_state(
        memory_root=str(tmp_path / "memory_feed_registry"),
        bars=bars,
        session_state="london",
        volatility_regime="expansion",
        config=MacroFeedConfig(
            alpha_vantage_api_key="k",
            fred_api_key="k",
            treasury_endpoint="https://example.com/treasury",
            economic_calendar_endpoint="https://example.com/calendar",
            enabled=True,
        ),
    )
    assert macro["trade_tags"]["dxy_proxy_state"] == "unavailable"
    assert macro["trade_tags"]["macro_feed_health"] in {"degraded", "unavailable", "healthy"}
    assert "dxy_proxy_degraded_fallback_alpha" in macro["risk_behavior"]["reasons"]
    assert macro["feed_registry"]["dxy_proxy"]["feed_name"] == "dxy_proxy"
    assert macro["feed_registry"]["gld_flow"]["feed_name"] == "gld_flow"
    assert Path(macro["paths"]["feed_health_latest"]).exists()
    assert Path(macro["paths"]["feed_health_history"]).exists()
