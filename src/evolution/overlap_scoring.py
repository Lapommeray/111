from __future__ import annotations

from typing import Any


class OverlapScoring:
    """Computes lexical + structural overlap to avoid duplicate proposals."""

    def evaluate(
        self,
        candidate_specs: list[dict[str, Any]],
        existing_signatures: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        normalized_existing = [self._normalize_signature(item) for item in existing_signatures]
        normalized_candidates = [self._normalize_signature(item) for item in candidate_specs]

        for index, spec in enumerate(candidate_specs):
            candidate_name = str(spec.get("candidate_name", ""))
            candidate_signature = normalized_candidates[index]

            best_existing_match = ""
            best_existing_score = 0.0
            best_existing_detail: dict[str, float] = {}
            best_existing_signature: dict[str, Any] = {}
            for existing in normalized_existing:
                score, detail = self._semantic_similarity(candidate_signature, existing)
                if score > best_existing_score:
                    best_existing_score = score
                    best_existing_match = str(existing.get("name", ""))
                    best_existing_detail = detail
                    best_existing_signature = existing

            best_candidate_match = ""
            best_candidate_score = 0.0
            for other_index, other in enumerate(normalized_candidates):
                if other_index == index:
                    continue
                score, _ = self._semantic_similarity(candidate_signature, other)
                if score > best_candidate_score:
                    best_candidate_score = score
                    best_candidate_match = str(other.get("name", ""))

            max_overlap_score = max(best_existing_score, best_candidate_score)
            structural_redundancy = (
                best_existing_detail.get("truth_class", 0.0) >= 1.0
                and best_existing_detail.get("inputs", 0.0) >= 0.99
                and best_existing_detail.get("outputs", 0.0) >= 0.99
                and best_existing_detail.get("constraints", 0.0) >= 0.99
                and best_existing_detail.get("purpose", 0.0) >= 0.15
            )
            is_duplicate_risk = max_overlap_score >= 0.9
            merge_candidate = max_overlap_score >= 0.7 or structural_redundancy

            results.append(
                {
                    "candidate_id": spec.get("candidate_id", "unknown"),
                    "candidate_name": candidate_name,
                    "best_existing_match": best_existing_match,
                    "existing_overlap_score": round(best_existing_score, 4),
                    "best_candidate_match": best_candidate_match,
                    "candidate_overlap_score": round(best_candidate_score, 4),
                    "overlap_score": round(max_overlap_score, 4),
                    "overlap_components": {
                        "truth_class": round(best_existing_detail.get("truth_class", 0.0), 4),
                        "purpose": round(best_existing_detail.get("purpose", 0.0), 4),
                        "inputs": round(best_existing_detail.get("inputs", 0.0), 4),
                        "outputs": round(best_existing_detail.get("outputs", 0.0), 4),
                        "constraints": round(best_existing_detail.get("constraints", 0.0), 4),
                    },
                    "is_duplicate_risk": is_duplicate_risk,
                    "merge_candidate": merge_candidate,
                    "structural_redundancy": structural_redundancy,
                    "best_existing_signature": {
                        "name": str(best_existing_signature.get("name", "")),
                        "truth_class": str(best_existing_signature.get("truth_class", "")),
                        "truth_class_rationale": str(best_existing_signature.get("truth_class_rationale", "")),
                        "purpose": str(best_existing_signature.get("purpose", "")),
                        "inputs": sorted(best_existing_signature.get("inputs", set())),
                        "outputs": sorted(best_existing_signature.get("outputs", set())),
                        "constraints": sorted(best_existing_signature.get("constraints", set())),
                    },
                }
            )
        return results

    def _normalize_signature(self, item: dict[str, Any]) -> dict[str, Any]:
        spec = item.get("spec", {}) if isinstance(item.get("spec"), dict) else {}
        purpose = str(spec.get("purpose", item.get("module_name", "")))
        return {
            "name": str(item.get("candidate_name", item.get("module_name", ""))),
            "truth_class": str(item.get("truth_class", "meta-intelligence")),
            "truth_class_rationale": str(item.get("truth_class_rationale", "")),
            "purpose": purpose,
            "purpose_tokens": self._tokenize(purpose),
            "inputs": set(self._iter_str(spec.get("inputs", []))),
            "outputs": set(self._iter_str(spec.get("outputs", []))),
            "constraints": set(self._iter_str(spec.get("constraints", []))),
        }

    def _semantic_similarity(self, left: dict[str, Any], right: dict[str, Any]) -> tuple[float, dict[str, float]]:
        truth_score = 1.0 if left.get("truth_class") == right.get("truth_class") else 0.0
        purpose_score = self._jaccard(left.get("purpose_tokens", set()), right.get("purpose_tokens", set()))
        input_score = self._jaccard(left.get("inputs", set()), right.get("inputs", set()))
        output_score = self._jaccard(left.get("outputs", set()), right.get("outputs", set()))
        constraint_score = self._jaccard(left.get("constraints", set()), right.get("constraints", set()))

        weighted = (
            (0.15 * truth_score)
            + (0.70 * purpose_score)
            + (0.05 * input_score)
            + (0.05 * output_score)
            + (0.05 * constraint_score)
        )
        return weighted, {
            "truth_class": truth_score,
            "purpose": purpose_score,
            "inputs": input_score,
            "outputs": output_score,
            "constraints": constraint_score,
        }

    def _iter_str(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def _tokenize(self, value: str) -> set[str]:
        return {t for t in value.lower().replace("-", "_").split("_") if t}

    def _jaccard(self, left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left.intersection(right)) / len(left.union(right))
