from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
import json
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.request import urlopen

JsonFetcher = Callable[[str], Any]
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
            for event in events:
                if not isinstance(event, dict):
                    continue
                impact_text = str(event.get("impact") or event.get("impact_label") or "").lower()
                if "high" in impact_text:
                    high_impact_count += 1
                title = str(event.get("title") or event.get("event") or "").lower()
                if any(token in title for token in ("fomc", "cpi", "nfp", "fed", "powell")):
                    major_event_count += 1
            state = "elevated" if (high_impact_count > 0 or major_event_count > 0) else "calm"
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
