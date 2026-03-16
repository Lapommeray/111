from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import json
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.request import urlopen

from src.utils import read_json_safe, write_json_atomic

JsonFetcher = Callable[[str], Any]
MILLISECOND_TIMESTAMP_THRESHOLD = 10_000_000_000
ALLOWED_MACRO_FEED_HOSTS = {
    "www.alphavantage.co",
    "api.stlouisfed.org",
    "moneymatter.me",
    "nfs.faireconomy.media",
}


def _validate_feed_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("macro_feed_url_invalid_scheme")
    if (parsed.netloc or "").lower() not in ALLOWED_MACRO_FEED_HOSTS:
        raise ValueError("macro_feed_url_host_not_allowed")


def _default_fetch_json(url: str) -> Any:
    _validate_feed_url(url)
    with urlopen(url, timeout=3.0) as response:  # nosec: B310
        return json.loads(response.read().decode("utf-8"))


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _safe_float(value: Any) -> float | None:
    try:
        text = str(value).strip()
        if not text or text == ".":
            return None
        return float(text)
    except Exception:
        return None


def _default_unavailable_feed_state(feed_name: str, reason_code: str = "feed_unavailable") -> dict[str, Any]:
    return {
        "feed": feed_name,
        "available": False,
        "stale": True,
        "state": "unavailable",
        "reason_codes": [reason_code],
        "metrics": {},
        "timestamp": _now_iso(),
    }


def _safe_tick_rate(tick: Any) -> float | None:
    if tick is None:
        return None
    if isinstance(tick, dict):
        for key in ("bid", "ask", "last"):
            value = _safe_float(tick.get(key))
            if value is not None and value > 0:
                return value
        return None
    for key in ("bid", "ask", "last"):
        value = _safe_float(getattr(tick, key, None))
        if value is not None and value > 0:
            return value
    return None


@dataclass(frozen=True)
class MT5DXYProxyAdapter:
    history_filename: str = "dxy_proxy_history.json"
    retention_records: int = 1000
    tick_fetcher: Callable[[list[str]], dict[str, Any]] | None = None

    def fetch_state(self, *, memory_root: str) -> dict[str, Any]:
        symbols = ["EURUSD", "USDJPY", "GBPUSD", "USDCAD", "USDSEK", "USDCHF"]
        # DXY-style exponents (proxy only, not official benchmark).
        exponents = {
            "EURUSD": -0.576,
            "USDJPY": 0.136,
            "GBPUSD": -0.119,
            "USDCAD": 0.091,
            "USDSEK": 0.042,
            "USDCHF": 0.036,
        }
        history_path = Path(memory_root) / "macro_state" / self.history_filename
        history = read_json_safe(history_path, default=[])
        if not isinstance(history, list):
            history = []

        try:
            rates = self._fetch_rates(symbols)
            missing = [symbol for symbol in symbols if symbol not in rates or rates[symbol] <= 0]
            if missing:
                return self._unavailable_state(
                    reason=f"missing_tick:{','.join(missing)}",
                    history=history,
                    history_path=history_path,
                    fallback_state="alpha_vantage_dxy_proxy",
                    status="degraded",
                    health_status="degraded",
                    confidence=0.35,
                )

            dxy_proxy_value = 50.14348112
            for symbol in symbols:
                dxy_proxy_value *= rates[symbol] ** exponents[symbol]
            dxy_proxy_value = round(dxy_proxy_value, 6)
            previous = history[-1]["proxy_value"] if history and isinstance(history[-1], dict) else None
            proxy_change = None
            if isinstance(previous, (int, float)) and previous != 0:
                proxy_change = round((dxy_proxy_value - float(previous)) / float(previous), 6)
            history.append({"timestamp": _now_iso(), "proxy_value": dxy_proxy_value})
            history = history[-max(1, int(self.retention_records)) :]
            write_json_atomic(history_path, history)
            state = "neutral_usd"
            if isinstance(proxy_change, (int, float)):
                if proxy_change >= 0.0015:
                    state = "strong_usd"
                elif proxy_change <= -0.0015:
                    state = "weak_usd"
            return {
                "feed": "dxy_proxy",
                "feed_name": "dxy_proxy",
                "available": True,
                "stale": False,
                "state": state,
                "status": "available",
                "health_status": "healthy",
                "last_update_timestamp": _now_iso(),
                "symbol_scope": "XAUUSD",
                "data_confidence": 0.85,
                "fallback_state": "none",
                "reason_codes": [],
                "benchmark_label": "not_official_benchmark_dxy",
                "metrics": {
                    "proxy_value": dxy_proxy_value,
                    "usd_proxy_change": proxy_change,
                    "pair_rates": {symbol: round(rates[symbol], 6) for symbol in symbols},
                    "recent_history": history[-20:],
                },
                "history_path": str(history_path),
                "timestamp": _now_iso(),
            }
        except Exception as exc:
            return self._unavailable_state(
                reason=f"request_failed:{type(exc).__name__}",
                history=history,
                history_path=history_path,
                fallback_state="alpha_vantage_dxy_proxy",
                status="degraded",
                health_status="degraded",
                confidence=0.3,
            )

    def _fetch_rates(self, symbols: list[str]) -> dict[str, float]:
        rates: dict[str, float] = {}
        if self.tick_fetcher is not None:
            payload = self.tick_fetcher(symbols)
            payload = payload if isinstance(payload, dict) else {}
            for symbol in symbols:
                rate = _safe_tick_rate(payload.get(symbol))
                if rate is not None and rate > 0:
                    rates[symbol] = rate
            return rates

        try:
            import MetaTrader5 as mt5  # type: ignore
        except Exception:
            return rates
        if not mt5.initialize():
            return rates
        try:
            for symbol in symbols:
                tick = mt5.symbol_info_tick(symbol)
                rate = _safe_tick_rate(tick)
                if rate is not None and rate > 0:
                    rates[symbol] = rate
        finally:
            mt5.shutdown()
        return rates

    def _unavailable_state(
        self,
        *,
        reason: str,
        history: list[Any],
        history_path: Path,
        fallback_state: str,
        status: str,
        health_status: str,
        confidence: float,
    ) -> dict[str, Any]:
        write_json_atomic(history_path, history[-max(1, int(self.retention_records)) :])
        return {
            "feed": "dxy_proxy",
            "feed_name": "dxy_proxy",
            "available": False,
            "stale": True,
            "state": "unavailable",
            "status": status,
            "health_status": health_status,
            "last_update_timestamp": _now_iso(),
            "symbol_scope": "XAUUSD",
            "data_confidence": confidence,
            "fallback_state": fallback_state,
            "reason_codes": [reason],
            "benchmark_label": "not_official_benchmark_dxy",
            "metrics": {
                "usd_proxy_change": None,
                "recent_history": history[-20:],
            },
            "history_path": str(history_path),
            "timestamp": _now_iso(),
        }


@dataclass(frozen=True)
class AlphaVantageAdapter:
    api_key: str
    fetcher: JsonFetcher = _default_fetch_json

    def fetch_dxy_proxy(self) -> dict[str, Any]:
        if not self.api_key:
            return {
                "feed": "alpha_vantage",
                "available": False,
                "stale": True,
                "state": "unavailable",
                "reason_codes": ["api_key_missing"],
                "metrics": {},
                "timestamp": _now_iso(),
            }
        params = urlencode(
            {
                "function": "FX_DAILY",
                "from_symbol": "EUR",
                "to_symbol": "USD",
                "outputsize": "compact",
                "apikey": self.api_key,
            }
        )
        url = f"https://www.alphavantage.co/query?{params}"
        try:
            payload = self.fetcher(url)
            series = payload.get("Time Series FX (Daily)", {}) if isinstance(payload, dict) else {}
            if not isinstance(series, dict) or not series:
                note = str(payload.get("Note", "")) if isinstance(payload, dict) else ""
                reason_codes = ["invalid_payload"]
                if note:
                    reason_codes.append("rate_limited")
                return {
                    "feed": "alpha_vantage",
                    "available": False,
                    "stale": True,
                    "state": "unavailable",
                    "reason_codes": reason_codes,
                    "metrics": {},
                    "timestamp": _now_iso(),
                }
            dates = sorted(series.keys(), reverse=True)
            latest_close = _safe_float(series.get(dates[0], {}).get("4. close"))
            prev_close = _safe_float(series.get(dates[1], {}).get("4. close")) if len(dates) > 1 else None
            if latest_close is None or prev_close is None or prev_close == 0:
                return {
                    "feed": "alpha_vantage",
                    "available": False,
                    "stale": True,
                    "state": "unavailable",
                    "reason_codes": ["insufficient_fx_series"],
                    "metrics": {},
                    "timestamp": _now_iso(),
                }
            eurusd_change = (latest_close - prev_close) / prev_close
            usd_proxy_change = -eurusd_change
            if usd_proxy_change >= 0.0015:
                state = "strong_usd"
            elif usd_proxy_change <= -0.0015:
                state = "weak_usd"
            else:
                state = "neutral_usd"
            return {
                "feed": "alpha_vantage",
                "available": True,
                "stale": False,
                "state": state,
                "reason_codes": [],
                "metrics": {
                    "proxy_pair": "EURUSD_inverse",
                    "latest_close": round(latest_close, 6),
                    "previous_close": round(prev_close, 6),
                    "usd_proxy_change": round(usd_proxy_change, 6),
                    "latest_date": dates[0],
                },
                "timestamp": _now_iso(),
            }
        except Exception as exc:
            return {
                "feed": "alpha_vantage",
                "available": False,
                "stale": True,
                "state": "unavailable",
                "reason_codes": [f"request_failed:{type(exc).__name__}"],
                "metrics": {},
                "timestamp": _now_iso(),
            }


@dataclass(frozen=True)
class FREDAdapter:
    api_key: str
    fetcher: JsonFetcher = _default_fetch_json

    def fetch_series(self, series_id: str) -> dict[str, Any]:
        if not self.api_key:
            return {
                "series_id": series_id,
                "available": False,
                "stale": True,
                "value": None,
                "previous_value": None,
                "change": None,
                "reason_codes": ["api_key_missing"],
            }
        params = urlencode(
            {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": "10",
            }
        )
        url = f"https://api.stlouisfed.org/fred/series/observations?{params}"
        try:
            payload = self.fetcher(url)
            observations = payload.get("observations", []) if isinstance(payload, dict) else []
            numeric: list[tuple[str, float]] = []
            for row in observations:
                if not isinstance(row, dict):
                    continue
                value = _safe_float(row.get("value"))
                if value is None:
                    continue
                numeric.append((str(row.get("date", "")), value))
                if len(numeric) >= 2:
                    break
            if not numeric:
                return {
                    "series_id": series_id,
                    "available": False,
                    "stale": True,
                    "value": None,
                    "previous_value": None,
                    "change": None,
                    "reason_codes": ["no_numeric_observations"],
                }
            latest_date, latest_value = numeric[0]
            previous_value = numeric[1][1] if len(numeric) > 1 else latest_value
            change = latest_value - previous_value
            return {
                "series_id": series_id,
                "available": True,
                "stale": False,
                "value": round(latest_value, 6),
                "previous_value": round(previous_value, 6),
                "change": round(change, 6),
                "latest_date": latest_date,
                "reason_codes": [],
            }
        except Exception as exc:
            return {
                "series_id": series_id,
                "available": False,
                "stale": True,
                "value": None,
                "previous_value": None,
                "change": None,
                "reason_codes": [f"request_failed:{type(exc).__name__}"],
            }

    def fetch_core_macro(self) -> dict[str, dict[str, Any]]:
        dgs10 = self.fetch_series("DGS10")
        dgs2 = self.fetch_series("DGS2")
        t10yie = self.fetch_series("T10YIE")
        real_rate = None
        if dgs10.get("value") is not None and t10yie.get("value") is not None:
            real_rate = round(float(dgs10["value"]) - float(t10yie["value"]), 6)
        return {
            "DGS10": dgs10,
            "DGS2": dgs2,
            "T10YIE": t10yie,
            "REAL_RATE_PROXY": {
                "series_id": "REAL_RATE_PROXY",
                "available": real_rate is not None,
                "stale": real_rate is None,
                "value": real_rate,
                "previous_value": None,
                "change": None,
                "reason_codes": [] if real_rate is not None else ["missing_components"],
            },
        }


@dataclass(frozen=True)
class TreasuryYieldsAdapter:
    endpoint: str
    fetcher: JsonFetcher = _default_fetch_json

    def fetch_yields(self) -> dict[str, Any]:
        try:
            payload = self.fetcher(self.endpoint)
            ten_year = _safe_float(self._find_numeric(payload, ["10", "ten"]))
            two_year = _safe_float(self._find_numeric(payload, ["2", "two"]))
            if ten_year is None or two_year is None:
                return {
                    "feed": "treasury",
                    "available": False,
                    "stale": True,
                    "state": "unavailable",
                    "reason_codes": ["missing_2y_10y_values"],
                    "metrics": {},
                    "timestamp": _now_iso(),
                }
            return {
                "feed": "treasury",
                "available": True,
                "stale": False,
                "state": "available",
                "reason_codes": [],
                "metrics": {
                    "yield_10y": round(ten_year, 6),
                    "yield_2y": round(two_year, 6),
                    "curve_10y_2y": round(ten_year - two_year, 6),
                },
                "timestamp": _now_iso(),
            }
        except Exception as exc:
            return {
                "feed": "treasury",
                "available": False,
                "stale": True,
                "state": "unavailable",
                "reason_codes": [f"request_failed:{type(exc).__name__}"],
                "metrics": {},
                "timestamp": _now_iso(),
            }

    def _find_numeric(self, payload: Any, key_hints: list[str]) -> Any:
        lowered_hints = [hint.lower() for hint in key_hints]
        if isinstance(payload, dict):
            for key, value in payload.items():
                key_text = str(key).lower()
                if any(hint in key_text for hint in lowered_hints):
                    num = _safe_float(value)
                    if num is not None:
                        return num
                nested = self._find_numeric(value, key_hints)
                if nested is not None:
                    return nested
        elif isinstance(payload, list):
            for item in payload:
                nested = self._find_numeric(item, key_hints)
                if nested is not None:
                    return nested
        return None


@dataclass(frozen=True)
class EconomicCalendarAdapter:
    endpoint: str
    fetcher: JsonFetcher = _default_fetch_json

    def fetch_events(self) -> dict[str, Any]:
        try:
            payload = self.fetcher(self.endpoint)
            events = payload if isinstance(payload, list) else []
            if not events:
                return {
                    "feed": "economic_calendar",
                    "available": False,
                    "stale": True,
                    "state": "unavailable",
                    "reason_codes": ["no_events"],
                    "metrics": {},
                    "timestamp": _now_iso(),
                }
            high_impact_count = 0
            major_event_count = 0
            upcoming_major_events_60m = 0
            recent_major_events_30m = 0
            now = datetime.now(tz=timezone.utc)
            for event in events:
                if not isinstance(event, dict):
                    continue
                impact_text = str(event.get("impact") or event.get("impact_label") or "").lower()
                if "high" in impact_text:
                    high_impact_count += 1
                title = str(event.get("title") or event.get("event") or "").lower()
                is_major = any(token in title for token in ("fomc", "cpi", "nfp", "fed", "powell"))
                if is_major:
                    major_event_count += 1
                    event_time = self._parse_event_time(event)
                    if event_time is not None:
                        minutes_delta = (event_time - now).total_seconds() / 60.0
                        if 0 <= minutes_delta <= 60:
                            upcoming_major_events_60m += 1
                        if -30 <= minutes_delta < 0:
                            recent_major_events_30m += 1
            state = "elevated" if (high_impact_count > 0 or major_event_count > 0) else "calm"
            if major_event_count > 0:
                event_type = "major_macro_release"
            elif high_impact_count > 0:
                event_type = "high_impact_release"
            else:
                event_type = "routine_calendar"
            return {
                "feed": "economic_calendar",
                "available": True,
                "stale": False,
                "state": state,
                "reason_codes": [],
                "metrics": {
                    "high_impact_count": high_impact_count,
                    "major_event_count": major_event_count,
                    "event_count": len(events),
                    "upcoming_major_events_60m": upcoming_major_events_60m,
                    "recent_major_events_30m": recent_major_events_30m,
                    "event_type": event_type,
                },
                "timestamp": _now_iso(),
            }
        except Exception as exc:
            return {
                "feed": "economic_calendar",
                "available": False,
                "stale": True,
                "state": "unavailable",
                "reason_codes": [f"request_failed:{type(exc).__name__}"],
                "metrics": {},
                "timestamp": _now_iso(),
            }

    def _parse_event_time(self, event: dict[str, Any]) -> datetime | None:
        for key in ("timestamp", "datetime", "date", "time"):
            raw = event.get(key)
            if raw is None:
                continue
            text = str(raw).strip()
            if not text:
                continue
            try:
                if text.isdigit():
                    ts = int(text)
                    if ts > MILLISECOND_TIMESTAMP_THRESHOLD:
                        ts = ts // 1000
                    return datetime.fromtimestamp(ts, tz=timezone.utc)
                normalized = text.replace("Z", "+00:00")
                parsed = datetime.fromisoformat(normalized)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except Exception:
                continue
        return None


@dataclass(frozen=True)
class COMEXOpenInterestAdapter:
    endpoint: str = ""
    fetcher: JsonFetcher = _default_fetch_json

    def fetch_state(self) -> dict[str, Any]:
        if not self.endpoint:
            return _default_unavailable_feed_state("comex_open_interest", "endpoint_not_configured")
        try:
            payload = self.fetcher(self.endpoint)
            value = _safe_float(payload.get("open_interest") if isinstance(payload, dict) else None)
            if value is None:
                return _default_unavailable_feed_state("comex_open_interest", "value_missing")
            return {
                "feed": "comex_open_interest",
                "available": True,
                "stale": False,
                "state": "available",
                "reason_codes": [],
                "metrics": {"open_interest": round(value, 4)},
                "timestamp": _now_iso(),
            }
        except Exception as exc:
            return _default_unavailable_feed_state("comex_open_interest", f"request_failed:{type(exc).__name__}")


@dataclass(frozen=True)
class GoldEtfFlowsAdapter:
    endpoint: str = ""
    fetcher: JsonFetcher = _default_fetch_json

    def fetch_state(self) -> dict[str, Any]:
        if not self.endpoint:
            return _default_unavailable_feed_state("gold_etf_flows", "endpoint_not_configured")
        try:
            payload = self.fetcher(self.endpoint)
            gld_flow = _safe_float(payload.get("gld") if isinstance(payload, dict) else None)
            iau_flow = _safe_float(payload.get("iau") if isinstance(payload, dict) else None)
            if gld_flow is None and iau_flow is None:
                return _default_unavailable_feed_state("gold_etf_flows", "value_missing")
            return {
                "feed": "gold_etf_flows",
                "available": True,
                "stale": False,
                "state": "available",
                "reason_codes": [],
                "metrics": {"gld_flow": gld_flow, "iau_flow": iau_flow},
                "timestamp": _now_iso(),
            }
        except Exception as exc:
            return _default_unavailable_feed_state("gold_etf_flows", f"request_failed:{type(exc).__name__}")


@dataclass(frozen=True)
class GoldOptionMagnetAdapter:
    endpoint: str = ""
    fetcher: JsonFetcher = _default_fetch_json

    def fetch_state(self) -> dict[str, Any]:
        if not self.endpoint:
            return _default_unavailable_feed_state("gold_option_magnet_levels", "endpoint_not_configured")
        try:
            payload = self.fetcher(self.endpoint)
            levels = payload.get("levels") if isinstance(payload, dict) else None
            if not isinstance(levels, list) or not levels:
                return _default_unavailable_feed_state("gold_option_magnet_levels", "levels_missing")
            return {
                "feed": "gold_option_magnet_levels",
                "available": True,
                "stale": False,
                "state": "available",
                "reason_codes": [],
                "metrics": {"levels": levels[:20]},
                "timestamp": _now_iso(),
            }
        except Exception as exc:
            return _default_unavailable_feed_state("gold_option_magnet_levels", f"request_failed:{type(exc).__name__}")


@dataclass(frozen=True)
class GoldPhysicalPremiumAdapter:
    endpoint: str = ""
    fetcher: JsonFetcher = _default_fetch_json

    def fetch_state(self) -> dict[str, Any]:
        if not self.endpoint:
            return _default_unavailable_feed_state("gold_physical_premium_discount", "endpoint_not_configured")
        try:
            payload = self.fetcher(self.endpoint)
            premium = _safe_float(payload.get("premium_discount") if isinstance(payload, dict) else None)
            if premium is None:
                return _default_unavailable_feed_state("gold_physical_premium_discount", "value_missing")
            return {
                "feed": "gold_physical_premium_discount",
                "available": True,
                "stale": False,
                "state": "available",
                "reason_codes": [],
                "metrics": {"premium_discount": round(premium, 6)},
                "timestamp": _now_iso(),
            }
        except Exception as exc:
            return _default_unavailable_feed_state(
                "gold_physical_premium_discount",
                f"request_failed:{type(exc).__name__}",
            )


@dataclass(frozen=True)
class CentralBankReserveAdapter:
    endpoint: str = ""
    fetcher: JsonFetcher = _default_fetch_json

    def fetch_state(self) -> dict[str, Any]:
        if not self.endpoint:
            return _default_unavailable_feed_state("central_bank_gold_reserves", "endpoint_not_configured")
        try:
            payload = self.fetcher(self.endpoint)
            reserve_change = _safe_float(payload.get("reserve_change_tonnes") if isinstance(payload, dict) else None)
            if reserve_change is None:
                return _default_unavailable_feed_state("central_bank_gold_reserves", "value_missing")
            return {
                "feed": "central_bank_gold_reserves",
                "available": True,
                "stale": False,
                "state": "available",
                "reason_codes": [],
                "metrics": {"reserve_change_tonnes": round(reserve_change, 6)},
                "timestamp": _now_iso(),
            }
        except Exception as exc:
            return _default_unavailable_feed_state("central_bank_gold_reserves", f"request_failed:{type(exc).__name__}")
