from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SymbolGuardConfig:
    primary_symbol: str = "XAUUSD"
    allowed_symbols: tuple[str, ...] = ("XAUUSD",)


class SymbolGuard:
    """Enforces XAUUSD-first runtime symbol constraints."""

    def __init__(self, config: SymbolGuardConfig | None = None) -> None:
        self.config = config or SymbolGuardConfig()

    def validate(self, symbol: str) -> dict[str, Any]:
        normalized = symbol.upper()
        allowed = {s.upper() for s in self.config.allowed_symbols}
        is_primary = normalized == self.config.primary_symbol.upper()
        allowed_symbol = normalized in allowed

        if not allowed_symbol:
            return {
                "ready": False,
                "status": "blocked",
                "reasons": [f"symbol_not_allowed:{normalized}"],
                "symbol": normalized,
                "primary_symbol": self.config.primary_symbol,
            }

        return {
            "ready": True,
            "status": "ready",
            "reasons": ["primary_symbol" if is_primary else "allowed_symbol"],
            "symbol": normalized,
            "primary_symbol": self.config.primary_symbol,
        }

    def validate_for_mt5(self, symbol: str) -> dict[str, Any]:
        validation = self.validate(symbol)
        return {
            "symbol": validation["symbol"],
            "primary_symbol": validation["primary_symbol"],
            "symbol_validity": bool(validation["ready"]),
            "symbol_status": validation["status"],
            "symbol_reasons": list(validation["reasons"]),
        }
