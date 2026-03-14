from __future__ import annotations

import json
import py_compile
from pathlib import Path
from typing import Any


class Verifier:
    """Runs visible validation checks for generated artifacts."""

    REQUIRED_PROPOSAL_KEYS = {
        "artifact_id": str,
        "kind": str,
        "triggering_gap": dict,
        "target_file": str,
        "content": str,
        "created_at": str,
    }

    REQUIRED_GAP_KEYS = {
        "gap_id": str,
        "reason": str,
        "target": str,
        "priority": str,
    }

    def verify(self, artifact_path: Path, proposal: dict[str, Any]) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []

        exists = artifact_path.exists()
        checks.append({"check": "artifact_exists", "passed": exists})
        if not exists:
            return {"passed": False, "checks": checks, "errors": ["artifact_missing"]}

        schema_ok, schema_errors = self._validate_proposal_schema(proposal)
        checks.append({"check": "proposal_schema", "passed": schema_ok})

        artifact_json_ok, artifact_json_errors = self._validate_artifact_json_payload(artifact_path, proposal)
        checks.append({"check": "artifact_json_payload", "passed": artifact_json_ok})

        compile_ok = True
        compile_error = ""
        if artifact_path.suffix == ".py":
            try:
                py_compile.compile(str(artifact_path), doraise=True)
            except Exception as exc:  # pragma: no cover
                compile_ok = False
                compile_error = str(exc)
        checks.append({"check": "python_compile", "passed": compile_ok})

        errors: list[str] = []
        if not all(item["passed"] for item in checks):
            errors.append("one_or_more_checks_failed")
        errors.extend(schema_errors)
        errors.extend(artifact_json_errors)
        if compile_error:
            errors.append(compile_error)

        return {
            "passed": len(errors) == 0,
            "checks": checks,
            "errors": errors,
        }

    def _validate_proposal_schema(self, proposal: dict[str, Any]) -> tuple[bool, list[str]]:
        errors: list[str] = []

        for key, expected_type in self.REQUIRED_PROPOSAL_KEYS.items():
            value = proposal.get(key)
            if not isinstance(value, expected_type):
                errors.append(f"invalid_or_missing_{key}")

        if proposal.get("kind") != "code_proposal":
            errors.append("invalid_kind")

        gap = proposal.get("triggering_gap", {})
        if isinstance(gap, dict):
            for key, expected_type in self.REQUIRED_GAP_KEYS.items():
                if not isinstance(gap.get(key), expected_type):
                    errors.append(f"invalid_or_missing_gap_{key}")
        else:
            errors.append("invalid_triggering_gap")

        target_file = str(proposal.get("target_file", ""))
        if not target_file.startswith(("src/", "config/", "memory/", "docs/")):
            errors.append("invalid_target_file_root")

        return len(errors) == 0, errors

    def _validate_artifact_json_payload(
        self,
        artifact_path: Path,
        proposal: dict[str, Any],
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []
        try:
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False, ["artifact_not_valid_json"]

        if payload != proposal:
            errors.append("artifact_payload_mismatch")

        return len(errors) == 0, errors
