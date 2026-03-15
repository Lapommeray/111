from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import csv

from src.mt5.symbol_guard import SymbolGuard


@dataclass(frozen=True)
class MT5Config:
    symbol: str = "XAUUSD"
    timeframe: str = "M5"
    bars: int = 200
    csv_fallback_path: str = "data/samples/xauusd.csv"
    max_data_age_seconds: int = 900
    fail_safe_blocked_state: bool = True


class MT5Adapter:
    """Fetches OHLCV bars for XAUUSD from MT5 when available, else from CSV fallback."""

    def __init__(self, config: MT5Config | None = None) -> None:
        self.config = config or MT5Config()
        self._last_readiness = self._default_readiness_state(data_source="uninitialized")

    def get_bars(self) -> list[dict[str, Any]]:
        if self.config.symbol.upper() != "XAUUSD":
            raise ValueError("MT5Adapter is currently restricted to XAUUSD.")

        bars, mt5_state = self._from_mt5()
        if bars:
            selected = bars[-self.config.bars :]
            self._last_readiness = self._build_controlled_readiness_state(
                bars=selected,
                data_source="mt5",
                mt5_state=mt5_state,
            )
            return selected

        selected = self._from_csv()
        self._last_readiness = self._build_controlled_readiness_state(
            bars=selected,
            data_source="csv_fallback",
            mt5_state=mt5_state,
        )
        return selected

    def get_controlled_readiness_state(self) -> dict[str, Any]:
        return dict(self._last_readiness)

    def _default_readiness_state(self, *, data_source: str) -> dict[str, Any]:
        return {
            "readiness_timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "data_source": data_source,
            "terminal_connectivity": False,
            "symbol_validity": False,
            "account_trading_permission": False,
            "data_freshness": False,
            "data_age_seconds": None,
            "fail_safe_blocked_state": bool(self.config.fail_safe_blocked_state),
            "live_execution_blocked": True,
            "order_execution_enabled": False,
            "ready_for_controlled_usage": False,
            "reason_codes": [],
        }

    def _assess_data_freshness(self, bars: list[dict[str, Any]]) -> tuple[bool, int | None]:
        if not bars:
            return False, None
        latest_time = int(bars[-1].get("time", 0))
        if latest_time <= 0:
            return False, None
        now_ts = int(datetime.now(tz=timezone.utc).timestamp())
        data_age_seconds = max(0, now_ts - latest_time)
        return data_age_seconds <= int(self.config.max_data_age_seconds), data_age_seconds

    def _build_controlled_readiness_state(
        self,
        *,
        bars: list[dict[str, Any]],
        data_source: str,
        mt5_state: dict[str, Any],
    ) -> dict[str, Any]:
        readiness = self._default_readiness_state(data_source=data_source)
        readiness.update(
            {
                "terminal_connectivity": bool(mt5_state.get("terminal_connectivity", False)),
                "symbol_validity": bool(mt5_state.get("symbol_validity", False)),
                "account_trading_permission": bool(mt5_state.get("account_trading_permission", False)),
            }
        )
        data_freshness, data_age_seconds = self._assess_data_freshness(bars)
        readiness["data_freshness"] = data_freshness
        readiness["data_age_seconds"] = data_age_seconds
        reasons = [str(reason) for reason in mt5_state.get("reason_codes", []) if str(reason).strip()]
        if data_source == "csv_fallback":
            reasons.append("csv_fallback_mode")
        if not data_freshness:
            reasons.append("data_stale_or_missing")
        if readiness["live_execution_blocked"]:
            reasons.append("live_execution_blocked_by_default")
        readiness["reason_codes"] = sorted(set(reasons))
        readiness["ready_for_controlled_usage"] = all(
            [
                readiness["terminal_connectivity"],
                readiness["symbol_validity"],
                readiness["account_trading_permission"],
                readiness["data_freshness"],
                readiness["fail_safe_blocked_state"],
                readiness["live_execution_blocked"],
                not readiness["order_execution_enabled"],
            ]
        )
        return readiness

    def _from_mt5(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        guard = SymbolGuard()
        symbol_validation = guard.validate_for_mt5(self.config.symbol)
        mt5_state = {
            "terminal_connectivity": False,
            "symbol_validity": bool(symbol_validation["symbol_validity"]),
            "account_trading_permission": False,
            "reason_codes": list(symbol_validation["symbol_reasons"]),
        }
        if not mt5_state["symbol_validity"]:
            return [], mt5_state

        try:
            import MetaTrader5 as mt5  # type: ignore
        except Exception:
            mt5_state["reason_codes"].append("mt5_module_unavailable")
            return [], mt5_state

        if not mt5.initialize():
            mt5_state["reason_codes"].append("mt5_initialize_failed")
            return [], mt5_state
        mt5_state["terminal_connectivity"] = True

        try:
            symbol_info = mt5.symbol_info(self.config.symbol)
            if symbol_info is None:
                mt5_state["symbol_validity"] = False
                mt5_state["reason_codes"].append("symbol_not_found_in_terminal")
            elif not bool(getattr(symbol_info, "visible", True)):
                symbol_select = getattr(mt5, "symbol_select", None)
                selected = bool(symbol_select(self.config.symbol, True)) if callable(symbol_select) else False
                mt5_state["symbol_validity"] = selected
                if not selected:
                    mt5_state["reason_codes"].append("symbol_not_visible")

            account_info_fn = getattr(mt5, "account_info", None)
            account_info = account_info_fn() if callable(account_info_fn) else None
            mt5_state["account_trading_permission"] = bool(
                account_info is not None and bool(getattr(account_info, "trade_allowed", False))
            )
            if not mt5_state["account_trading_permission"]:
                mt5_state["reason_codes"].append("account_trade_not_allowed")

            timeframe_map = {
                "M1": mt5.TIMEFRAME_M1,
                "M5": mt5.TIMEFRAME_M5,
                "M15": mt5.TIMEFRAME_M15,
                "H1": mt5.TIMEFRAME_H1,
                "H4": mt5.TIMEFRAME_H4,
            }
            tf = timeframe_map.get(self.config.timeframe.upper(), mt5.TIMEFRAME_M5)

            rates = mt5.copy_rates_from_pos(self.config.symbol, tf, 0, self.config.bars)
        finally:
            mt5.shutdown()

        if rates is None:
            mt5_state["reason_codes"].append("mt5_rates_unavailable")
            return [], mt5_state

        return (
            [
                {
                    "time": int(r["time"]),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "tick_volume": float(r["tick_volume"]),
                }
                for r in rates
            ],
            mt5_state,
        )

    def _from_csv(self) -> list[dict[str, Any]]:
        path = Path(self.config.csv_fallback_path)
        if not path.exists():
            raise FileNotFoundError(
                f"No MT5 data available and CSV fallback not found: {path}"
            )

        with path.open("r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            bars = []
            for row in reader:
                bars.append(
                    {
                        "time": int(row["time"]),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "tick_volume": float(row.get("tick_volume", 0.0)),
                    }
                )
        if not bars:
            raise ValueError(f"CSV fallback is empty: {path}")
        return bars[-self.config.bars :]
