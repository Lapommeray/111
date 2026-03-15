from __future__ import annotations

from src.module_factory import ModuleFactory
from src.pipeline import OversoulDirector


def test_module_factory_discovers_expected_categories() -> None:
    factory = ModuleFactory()
    modules = factory.list_all_modules()

    for category in ("features", "filters", "scoring", "memory", "indicator", "mt5"):
    for category in ("features", "filters", "scoring", "memory", "evolution", "indicator", "mt5"):
        assert category in modules

    assert "market_structure" in modules["features"]
    assert "loss_blocker" in modules["filters"]
    assert "confidence_score" in modules["scoring"]
    assert "self_inspector" in modules["evolution"]


def test_module_factory_count_and_create() -> None:
    factory = ModuleFactory()
    assert factory.get_module_count() > 0

    created = factory.create_module("filters", "loss_blocker")
    assert hasattr(created, "evaluate")


def test_oversoul_director_exposes_discovered_modules() -> None:
    director = OversoulDirector()
    discovered = director.discovered_as_dict()

    assert "features" in discovered
    assert "market_structure" in discovered["features"]
