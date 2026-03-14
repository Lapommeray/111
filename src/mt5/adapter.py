from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import csv


@dataclass(frozen=True)
class MT5Config:
    symbol: str = "XAUUSD"
    timeframe: str = "M5"
    bars: int = 200
    csv_fallback_path: str = "data/samples/xauusd.csv"


class MT5Adapter:
    """Fetches OHLCV bars for XAUUSD from MT5 when available, else from CSV fallback."""

    def __init__(self, config: MT5Config | None = None) -> None:
        self.config = config or MT5Config()

    def get_bars(self) -> list[dict[str, Any]]:
        if self.config.symbol.upper() != "XAUUSD":
            raise ValueError("MT5Adapter is currently restricted to XAUUSD.")

        bars = self._from_mt5()
        if bars:
            return bars[-self.config.bars :]

        return self._from_csv()

    def _from_mt5(self) -> list[dict[str, Any]]:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except Exception:
            return []

        if not mt5.initialize():
            return []

        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
        }
        tf = timeframe_map.get(self.config.timeframe.upper(), mt5.TIMEFRAME_M5)

        rates = mt5.copy_rates_from_pos(self.config.symbol, tf, 0, self.config.bars)
        mt5.shutdown()

        if rates is None:
            return []

        return [
            {
                "time": int(r["time"]),
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "tick_volume": float(r["tick_volume"]),
            }
            for r in rates
        ]

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
