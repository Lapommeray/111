from __future__ import annotations

from pathlib import Path
from typing import Any

from src.module_factory import ModuleFactory
from src.pipeline import OversoulDirector
from src.utils import read_json_safe


class SelfInspector:
    """Scans project wiring and reports architectural gaps."""

    def __init__(self, project_root: Path, generated_registry_path: Path, evolution_registry_path: Path) -> None:
        self.project_root = project_root
        self.generated_registry_path = generated_registry_path
        self.evolution_registry_path = evolution_registry_path

    def inspect(self) -> dict[str, Any]:
        factory = ModuleFactory(project_root=self.project_root / "src")
        director = OversoulDirector()

        tests_dir = self.project_root / "src" / "tests"
        test_text = "\n".join(
            p.read_text(encoding="utf-8") for p in sorted(tests_dir.glob("test_*.py"))
        )

        module_map_keys = set(director.as_dict().keys())
        hook_sources = {v["source_module"] for v in director.hooks_as_dict().values()}

        missing_tests: list[str] = []
        for category in ("features", "filters", "scoring", "memory", "indicator", "mt5"):
            for module_name in factory.get_category_modules(category):
                if module_name not in test_text:
                    missing_tests.append(module_name)

        expected_hook_modules = self._expected_hook_modules()
        missing_hooks = sorted(expected_hook_modules - hook_sources)

        pipeline_text = (self.project_root / "src" / "pipeline.py").read_text(encoding="utf-8")
        missing_state_contributions = sorted([key for key in module_map_keys if key not in pipeline_text])

        generated_registry = read_json_safe(self.generated_registry_path, default={"artifacts": []})
        generated_artifacts = generated_registry.get("artifacts", []) if isinstance(generated_registry, dict) else []

        evolution_registry = read_json_safe(self.evolution_registry_path, default={"entries": []})
        evolution_entries = evolution_registry.get("entries", []) if isinstance(evolution_registry, dict) else []

        registered_paths = {str(item.get("artifact_path", "")) for item in generated_artifacts}
        missing_registrations: list[str] = []
        for entry in evolution_entries:
            path = str(entry.get("artifact_path", ""))
            if path and path not in registered_paths:
                missing_registrations.append(path)

        dead_modules = self._dead_modules(factory, module_map_keys, hook_sources)

        broken_arch_links = sorted([src for src in hook_sources if src not in module_map_keys])

        return {
            "missing_tests": sorted(set(missing_tests)),
            "missing_hooks": missing_hooks,
            "missing_state_contributions": missing_state_contributions,
            "missing_registrations": sorted(set(missing_registrations)),
            "dead_modules": dead_modules,
            "broken_arch_links": broken_arch_links,
        }

    def _expected_hook_modules(self) -> set[str]:
        connectors_path = self.project_root / "config" / "connectors.json"
        payload = read_json_safe(connectors_path, default={"hooks": []})
        hooks = payload.get("hooks", []) if isinstance(payload, dict) else []
        expected: set[str] = set()
        for hook in hooks:
            if isinstance(hook, dict) and hook.get("enabled", False):
                source = str(hook.get("source_module", "")).strip()
                if source:
                    expected.add(source)
        return expected

    def _dead_modules(
        self,
        factory: ModuleFactory,
        module_map_keys: set[str],
        hook_sources: set[str],
    ) -> list[str]:
        referenced = self._collect_module_references()
        dead_modules: list[str] = []

        for category, modules in factory.list_all_modules().items():
            for module_name in modules:
                marker = f"{category}.{module_name}"
                if module_name in module_map_keys:
                    continue
                if module_name in hook_sources:
                    continue
                if marker in referenced:
                    continue
                dead_modules.append(marker)

        return sorted(set(dead_modules))

    def _collect_module_references(self) -> set[str]:
        references: set[str] = set()

        source_files = list((self.project_root / "src").glob("**/*.py"))
        run_file = self.project_root / "run.py"
        if run_file.exists():
            source_files.append(run_file)

        for py_file in source_files:
            if "/tests/" in py_file.as_posix():
                continue
            text = py_file.read_text(encoding="utf-8")
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("from src.") or stripped.startswith("import src."):
                    token = stripped.replace("from ", "").replace("import ", "").split()[0]
                    if token.startswith("src."):
                        parts = token.split(".")
                        if len(parts) >= 3:
                            references.add(f"{parts[1]}.{parts[2]}")
        return references
