from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from inspect import Parameter, getmembers, isclass, signature
from pathlib import Path
from types import ModuleType
from typing import Any


@dataclass(frozen=True)
class FactoryConfig:
    root_package: str = "src"
    categories: tuple[str, ...] = (
        "features",
        "filters",
        "scoring",
        "memory",
        "indicator",
        "mt5",
    )


class ModuleFactory:
    """Visible filesystem-backed module registry and loader.

    This class is an architectural helper only. It discovers importable modules,
    exposes category/module listings, and supports optional instantiation for
    module classes that use zero-argument constructors.
    """

    def __init__(self, config: FactoryConfig | None = None, project_root: Path | None = None) -> None:
        self.config = config or FactoryConfig()
        self.project_root = project_root or Path(__file__).resolve().parent
        self._registry: dict[str, list[str]] = self._discover_registry()

    def _discover_registry(self) -> dict[str, list[str]]:
        registry: dict[str, list[str]] = {}

        for category in self.config.categories:
            category_path = self.project_root / category
            if not category_path.exists() or not category_path.is_dir():
                registry[category] = []
                continue

            modules = sorted(
                p.stem
                for p in category_path.glob("*.py")
                if p.stem != "__init__" and not p.stem.startswith("_")
            )
            registry[category] = modules

        return registry

    def refresh(self) -> None:
        self._registry = self._discover_registry()

    def list_all_modules(self) -> dict[str, list[str]]:
        return {category: list(modules) for category, modules in self._registry.items()}

    def get_category_modules(self, category: str) -> list[str]:
        if category not in self._registry:
            raise ValueError(f"Unknown module category: {category}")
        return list(self._registry[category])

    def get_module_count(self) -> int:
        return sum(len(modules) for modules in self._registry.values())

    def create_module(self, category: str, module_name: str) -> Any:
        if category not in self._registry:
            raise ValueError(f"Unknown module category: {category}")
        if module_name not in self._registry[category]:
            raise ValueError(f"Module '{module_name}' is not registered in category '{category}'")

        module = import_module(f"{self.config.root_package}.{category}.{module_name}")
        instance = self._instantiate_first_compatible_class(module)
        return instance if instance is not None else module

    def create_all_modules(self) -> dict[str, dict[str, Any]]:
        created: dict[str, dict[str, Any]] = {}

        for category, modules in self._registry.items():
            created[category] = {}
            for module_name in modules:
                created[category][module_name] = self.create_module(category, module_name)

        return created

    @staticmethod
    def _instantiate_first_compatible_class(module: ModuleType) -> Any | None:
        for _, klass in getmembers(module, isclass):
            if klass.__module__ != module.__name__:
                continue

            init_signature = signature(klass.__init__)
            params = [p for p in init_signature.parameters.values() if p.name != "self"]

            has_required_args = any(
                p.default is Parameter.empty
                and p.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
                for p in params
            )
            if has_required_args:
                continue

            return klass()

        return None
