from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from src.evolution.candidate_module_factory import CandidateModuleFactory
from src.evolution.governance_report import build_governance_report
from src.evolution.hypothesis_registry import HypothesisRegistry
from src.evolution.overlap_scoring import OverlapScoring
from src.utils import read_json_safe, write_json_atomic


class KnowledgeExpansionOrchestrator:
    """Phase A orchestrator for hypothesis->candidate->governance JSON outputs."""

    ALLOWED_TRUTH_CLASSES = {
        "regime",
        "participation",
        "liquidity",
        "timing",
        "failure",
        "meta-intelligence",
    }

    MIN_SAMPLES_KEEP = 10
    MIN_SAMPLES_HOLD = 6
    MIN_ALIGNMENT_KEEP = 0.45
    MIN_ALIGNMENT_HOLD = 0.25
    MIN_ABS_DELTA_KEEP = 0.035
    MIN_ABS_DELTA_HOLD = 0.015
    MIN_CONSISTENCY_KEEP = 0.65
    MIN_CONSISTENCY_HOLD = 0.5

    MIN_BLOCKER_COUNT_KEEP = 3
    MIN_BLOCKER_COUNT_HOLD = 2
    MIN_PROTECTIVE_RATIO_KEEP = 0.3
    MIN_PROTECTIVE_RATIO_HOLD = 0.2

    def __init__(self, root: Path, candidate_limit: int = 6) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.candidate_limit = max(1, candidate_limit)
        self.registry = HypothesisRegistry(self.root / "candidate_hypothesis_registry.json")
        self.candidate_factory = CandidateModuleFactory()
        self.overlap = OverlapScoring()

    def run(self, replay_report: dict[str, Any]) -> dict[str, Any]:
        generated_hypotheses = self._generate_hypotheses(replay_report)
        prioritized_hypotheses = self._prioritize_hypotheses(generated_hypotheses)
        hypotheses = self._merge_near_duplicate_hypotheses(prioritized_hypotheses)[: self.candidate_limit]
        registered = [self.registry.register(h) for h in hypotheses]
        merged_map = {str(item.get("hypothesis_id", "")): item for item in hypotheses}
        for item in registered:
            merged = merged_map.get(str(item.get("hypothesis_id", "")), {})
            if "evidence_history" in merged:
                item["evidence_history"] = merged.get("evidence_history", [])
            if "merged_hypothesis_ids" in merged:
                item["merged_hypothesis_ids"] = merged.get("merged_hypothesis_ids", [])

        candidate_specs = self.candidate_factory.generate(registered)
        existing_signatures = self._extract_existing_signatures(replay_report)
        overlap_report = self.overlap.evaluate(candidate_specs, existing_signatures)

        decisions = self._make_decisions(registered, candidate_specs, overlap_report)
        validated_knowledge_registry_path = self._persist_validated_knowledge_registry(
            hypotheses=registered,
            candidate_specs=candidate_specs,
            decisions=decisions,
        )
        governance_summary = build_governance_report(decisions)

        artifact_paths = self._write_artifacts(
            hypotheses=registered,
            candidate_specs=candidate_specs,
            overlap_report=overlap_report,
            decisions=decisions,
            summary=governance_summary,
            validated_knowledge_registry_path=validated_knowledge_registry_path,
        )

        return {
            "enabled": True,
            "candidate_count": len(candidate_specs),
            "decision_summary": governance_summary,
            "artifact_paths": artifact_paths,
            "sandbox_candidates_path": artifact_paths["sandbox_candidates"],
            "validated_knowledge_registry_path": artifact_paths["validated_knowledge_registry"],
            "decisions": decisions,
            "governance_law": {
                "required_gates": [
                    "hypothesis_clarity",
                    "replay_usefulness",
                    "non_duplication",
                    "measurable_contribution",
                    "no_forbidden_core_mutation",
                ],
                "allowed_decisions": ["KEEP", "MERGE", "REJECT", "HOLD_FOR_MORE_DATA"],
            },
        }

    def _generate_hypotheses(self, replay_report: dict[str, Any]) -> list[dict[str, Any]]:
        module_report = replay_report.get("module_contribution_report", {})
        blocker_report = replay_report.get("blocker_effect_report", {})
        session_report = replay_report.get("session_report", {})
        runtime_context = self._build_runtime_context(replay_report)

        hypotheses: list[dict[str, Any]] = []

        modules = module_report.get("modules", {}) if isinstance(module_report, dict) else {}
        for name, stats in modules.items():
            if not isinstance(stats, dict):
                continue

            action_alignment = self._normalize_action_alignment(stats)
            aligned_hits = int(action_alignment["aligned"])
            misaligned_hits = int(action_alignment["misaligned"])
            samples = int(stats.get("samples", 0))
            alignment_strength = float(action_alignment.get("alignment_ratio", 0.0))
            avg_delta = float(stats.get("avg_confidence_delta", 0.0))
            direction_consistency = self._direction_consistency(stats, samples)

            truth_class = self._truth_class_from_module_name(str(name))
            truth_rationale = self._truth_class_rationale(str(name), truth_class)
            usefulness_scope = self._determine_usefulness_scope(runtime_context)

            statement = self._build_module_hypothesis_statement(
                module_name=str(name),
                truth_class=truth_class,
                avg_delta=avg_delta,
                alignment_strength=alignment_strength,
                consistency=direction_consistency,
                context=runtime_context,
                usefulness_scope=usefulness_scope,
            )
            hypotheses.append(
                {
                    "truth_class": truth_class,
                    "truth_class_rationale": truth_rationale,
                    "usefulness_scope": usefulness_scope,
                    "statement": statement,
                    "evidence": {
                        "module_name": name,
                        "samples": samples,
                        "avg_confidence_delta": avg_delta,
                        "directional_alignment": aligned_hits,
                        "misalignment": misaligned_hits,
                        "alignment_strength": round(alignment_strength, 4),
                        "directional_consistency": round(direction_consistency, 4),
                        "action_alignment": action_alignment,
                        "regime_specific_alignment": stats.get("regime_specific_alignment", {}),
                        "contradiction_reduction_proxy": float(stats.get("contradiction_reduction_proxy", 0.0)),
                        "blocker_protection_strength": float(stats.get("blocker_protection_strength", 0.0)),
                        "confidence_calibration_shift": float(stats.get("confidence_calibration_shift", 0.0)),
                        "drawdown_prevention_proxy": float(stats.get("drawdown_prevention_proxy", 0.0)),
                        "context": runtime_context,
                    },
                    "source": "module_contribution_report",
                    "status": "candidate",
                }
            )

        top_reasons = blocker_report.get("top_reasons", []) if isinstance(blocker_report, dict) else []
        blocked_total = int(blocker_report.get("blocked_total", 0)) if isinstance(blocker_report, dict) else 0
        protective_hits = int(blocker_report.get("protective_proxy_hits", 0)) if isinstance(blocker_report, dict) else 0
        denominator = max(1, blocked_total, protective_hits)

        for reason in top_reasons[:2]:
            reason_name = str(reason.get("reason", "unknown")) if isinstance(reason, dict) else "unknown"
            reason_count = int(reason.get("count", 0)) if isinstance(reason, dict) else 0
            protective_ratio = (reason_count / denominator) if denominator > 0 else 0.0
            usefulness_scope = "conditional"
            hypotheses.append(
                {
                    "truth_class": "failure",
                    "truth_class_rationale": "Blocker reasons map to failure truth because they represent risk conditions that prevented execution.",
                    "usefulness_scope": usefulness_scope,
                    "statement": (
                        f"Assess blocker reason {reason_name} in {runtime_context['dominant_session']} context: "
                        f"count {reason_count}, protective ratio {protective_ratio:.2f}; useful only when this failure pattern recurs."
                    ),
                    "evidence": {
                        "reason": reason_name,
                        "count": reason_count,
                        "blocked_total": blocked_total,
                        "protective_proxy_hits": protective_hits,
                        "protective_ratio": round(protective_ratio, 4),
                        "context": runtime_context,
                    },
                    "source": "blocker_effect_report",
                    "status": "candidate",
                }
            )

        sessions = session_report.get("sessions", {}) if isinstance(session_report, dict) else {}
        for session_name, stats in list(sessions.items())[:2]:
            blocked = int(stats.get("blocked", 0)) if isinstance(stats, dict) else 0
            total = int(stats.get("samples", stats.get("total", 0))) if isinstance(stats, dict) else 0
            block_rate = (blocked / total) if total > 0 else 0.0
            usefulness_scope = "conditional"
            hypotheses.append(
                {
                    "truth_class": "timing",
                    "truth_class_rationale": "Session-derived behavior belongs to timing truth because it conditions when actions are reliable.",
                    "usefulness_scope": usefulness_scope,
                    "statement": (
                        f"Assess timing rule for session={session_name}: blocked {blocked}/{total} (rate {block_rate:.2f}) "
                        f"under regime_proxy={runtime_context['regime_proxy']}; usefulness is conditional to this session context."
                    ),
                    "evidence": {
                        "session": session_name,
                        "blocked": blocked,
                        "total": total,
                        "block_rate": round(block_rate, 4),
                        "context": runtime_context,
                    },
                    "source": "session_report",
                    "status": "candidate",
                }
            )

        for index, item in enumerate(hypotheses, start=1):
            item["hypothesis_id"] = f"phase_a_{index:03d}"
            truth_class = str(item.get("truth_class", "meta-intelligence"))
            if truth_class not in self.ALLOWED_TRUTH_CLASSES:
                item["truth_class"] = "meta-intelligence"

        return hypotheses

    def _merge_near_duplicate_hypotheses(self, hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for hypothesis in hypotheses:
            matched = False
            for existing in merged:
                if self._is_near_duplicate_hypothesis(existing, hypothesis):
                    existing_history = (
                        list(existing.get("evidence_history", []))
                        if isinstance(existing.get("evidence_history"), list)
                        else []
                    )
                    incoming_evidence = hypothesis.get("evidence", {})
                    if incoming_evidence:
                        existing_history.append(incoming_evidence)
                    existing["evidence_history"] = existing_history

                    merged_ids = (
                        list(existing.get("merged_hypothesis_ids", []))
                        if isinstance(existing.get("merged_hypothesis_ids"), list)
                        else []
                    )
                    incoming_id = str(hypothesis.get("hypothesis_id", ""))
                    if incoming_id and incoming_id not in merged_ids:
                        merged_ids.append(incoming_id)
                    existing["merged_hypothesis_ids"] = merged_ids
                    matched = True
                    break

            if not matched:
                entry = dict(hypothesis)
                entry["evidence_history"] = [entry.get("evidence", {})] if entry.get("evidence", {}) else []
                entry["merged_hypothesis_ids"] = [str(entry.get("hypothesis_id", ""))]
                merged.append(entry)

        return merged

    def _is_near_duplicate_hypothesis(self, left: dict[str, Any], right: dict[str, Any]) -> bool:
        if str(left.get("truth_class", "")) != str(right.get("truth_class", "")):
            return False
        source = str(left.get("source", ""))
        if source != str(right.get("source", "")):
            return False

        left_evidence = left.get("evidence", {}) if isinstance(left.get("evidence"), dict) else {}
        right_evidence = right.get("evidence", {}) if isinstance(right.get("evidence"), dict) else {}

        if source == "module_contribution_report":
            if str(left_evidence.get("module_name", "")) != str(right_evidence.get("module_name", "")):
                return False
        elif source == "blocker_effect_report":
            if str(left_evidence.get("reason", "")) != str(right_evidence.get("reason", "")):
                return False
        elif source == "session_report":
            if str(left_evidence.get("session", "")) != str(right_evidence.get("session", "")):
                return False

        left_statement = str(left.get("statement", "")).strip().lower()
        right_statement = str(right.get("statement", "")).strip().lower()
        if not left_statement or not right_statement:
            return False

        similarity = SequenceMatcher(a=left_statement, b=right_statement).ratio()
        return similarity >= 0.9

    def _truth_class_from_module_name(self, module_name: str) -> str:
        name = module_name.lower()
        if "regime" in name or "session" in name:
            return "regime" if "regime" in name else "timing"
        if "liquid" in name or "fvg" in name:
            return "liquidity"
        if "spread" in name or "volatility" in name:
            return "participation"
        if "filter" in name or "destruct" in name or "block" in name:
            return "failure"
        if "routing" in name or "fusion" in name or "confidence" in name:
            return "meta-intelligence"
        return "meta-intelligence"

    def _truth_class_rationale(self, module_name: str, truth_class: str) -> str:
        rationale_map = {
            "regime": "Module signal appears to classify environment state (trend/rotation/phase), so it is mapped to regime truth.",
            "participation": "Module reflects intensity/commitment of moves, which maps to participation truth.",
            "liquidity": "Module references sweep/gap/liquidity structures, so it belongs to liquidity truth.",
            "timing": "Module relates to session/time-window behavior, so it is timing truth.",
            "failure": "Module is a blocker/filter profile; these encode failure prevention conditions.",
            "meta-intelligence": "Module contributes routing/fusion/diagnostic behavior used to govern other evidence.",
        }
        return f"{rationale_map.get(truth_class, rationale_map['meta-intelligence'])} source={module_name}."

    def _build_module_hypothesis_statement(
        self,
        module_name: str,
        truth_class: str,
        avg_delta: float,
        alignment_strength: float,
        consistency: float,
        context: dict[str, Any],
        usefulness_scope: str,
    ) -> str:
        return (
            f"Evaluate {module_name} as {truth_class} truth in session={context['dominant_session']} "
            f"with regime_proxy={context['regime_proxy']}: avg confidence delta {avg_delta:.3f}, "
            f"alignment strength {alignment_strength:.2f}, consistency {consistency:.2f}. "
            f"Usefulness scope={usefulness_scope}; validate this as {'condition-bound' if usefulness_scope == 'conditional' else 'general'} contribution."
        )

    def _build_runtime_context(self, replay_report: dict[str, Any]) -> dict[str, Any]:
        session_payload = replay_report.get("session_report", {})
        sessions = session_payload.get("sessions", {}) if isinstance(session_payload, dict) else {}
        dominant_session = "unknown"
        dominant_session_ratio = 0.0
        total_session_samples = sum(
            int(v.get("samples", v.get("total", 0))) for v in sessions.values() if isinstance(v, dict)
        )
        if sessions:
            best_name = "unknown"
            best_count = -1
            for name, payload in sessions.items():
                if not isinstance(payload, dict):
                    continue
                count = int(payload.get("samples", payload.get("total", 0)))
                if count > best_count:
                    best_count = count
                    best_name = str(name)
            dominant_session = best_name
            dominant_session_ratio = (best_count / total_session_samples) if total_session_samples > 0 else 0.0

        blocker_payload = replay_report.get("blocker_effect_report", {})
        top_reasons = blocker_payload.get("top_reasons", []) if isinstance(blocker_payload, dict) else []
        top_blocker_reason = "none"
        if top_reasons and isinstance(top_reasons[0], dict):
            top_blocker_reason = str(top_reasons[0].get("reason", "none"))

        action_distribution = replay_report.get("action_distribution", {})
        confidence_distribution = replay_report.get("confidence_distribution", {})

        regime_proxy = "mixed"
        if isinstance(confidence_distribution, dict):
            high = int(confidence_distribution.get("high", 0))
            medium = int(confidence_distribution.get("medium", 0))
            low = int(confidence_distribution.get("low", 0))
            if high > (medium + low):
                regime_proxy = "high_confidence_bias"
            elif low >= high:
                regime_proxy = "low_confidence_bias"

        return {
            "dominant_session": dominant_session,
            "dominant_session_ratio": round(dominant_session_ratio, 4),
            "top_blocker_reason": top_blocker_reason,
            "regime_proxy": regime_proxy,
            "action_distribution": action_distribution if isinstance(action_distribution, dict) else {},
            "confidence_distribution": confidence_distribution if isinstance(confidence_distribution, dict) else {},
        }

    def _determine_usefulness_scope(self, context: dict[str, Any]) -> str:
        session_ratio = float(context.get("dominant_session_ratio", 0.0))
        top_blocker = str(context.get("top_blocker_reason", "none"))
        if session_ratio >= 0.6 or top_blocker != "none":
            return "conditional"
        return "general"

    def _extract_existing_signatures(self, replay_report: dict[str, Any]) -> list[dict[str, Any]]:
        modules = replay_report.get("module_contribution_report", {}).get("modules", {})
        if not isinstance(modules, dict):
            return []

        records = replay_report.get("records", []) if isinstance(replay_report.get("records"), list) else []
        module_behavior = self._collect_module_behavior(records)
        runtime_context = self._build_runtime_context(replay_report)

        signatures: list[dict[str, Any]] = []
        for module_name in sorted(modules.keys()):
            module_key = str(module_name)
            stats = modules.get(module_name, {}) if isinstance(modules.get(module_name), dict) else {}
            truth_class = self._truth_class_from_module_name(module_key)
            rationale = self._truth_class_rationale(module_key, truth_class)
            behavior = module_behavior.get(module_key, {})

            purpose = self._build_existing_module_purpose(
                module_name=module_key,
                truth_class=truth_class,
                truth_rationale=rationale,
                stats=stats,
                behavior=behavior,
                context=runtime_context,
            )

            signatures.append(
                {
                    "module_name": module_key,
                    "truth_class": truth_class,
                    "truth_class_rationale": rationale,
                    "spec": {
                        "purpose": purpose,
                        "inputs": ["advanced_modules", "signal", "status_panel", "bars_context"],
                        "outputs": ["direction_vote", "confidence_delta", "reasons", "payload", "health"],
                        "constraints": [
                            "xauusd_first_only",
                            "no_core_strategy_mutation",
                            "json_friendly_artifact_only",
                            "replay_only_governance_comparison",
                        ],
                    },
                }
            )
        return signatures

    def _collect_module_behavior(self, records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        behavior: dict[str, dict[str, Any]] = {}
        if not records:
            return behavior

        for record in records:
            signal = record.get("signal", {}) if isinstance(record.get("signal"), dict) else {}
            advanced = signal.get("advanced_modules", {}) if isinstance(signal.get("advanced_modules"), dict) else {}
            module_results = advanced.get("module_results", {}) if isinstance(advanced.get("module_results"), dict) else {}

            for module_name, payload in module_results.items():
                name = str(module_name)
                if not isinstance(payload, dict):
                    continue
                entry = behavior.setdefault(
                    name,
                    {
                        "votes": [],
                        "avg_delta_samples": [],
                        "payload_keys": set(),
                        "reason_examples": set(),
                    },
                )
                entry["votes"].append(str(payload.get("direction_vote", "neutral")))
                entry["avg_delta_samples"].append(float(payload.get("confidence_delta", 0.0)))

                payload_body = payload.get("payload", {})
                if isinstance(payload_body, dict):
                    entry["payload_keys"].update(str(k) for k in payload_body.keys())

                reasons = payload.get("reasons", [])
                if isinstance(reasons, list):
                    for r in reasons[:2]:
                        entry["reason_examples"].add(str(r))

        out: dict[str, dict[str, Any]] = {}
        for module_name, entry in behavior.items():
            votes = entry.get("votes", [])
            deltas = entry.get("avg_delta_samples", [])
            dominant_vote = "neutral"
            if votes:
                dominant_vote = max(set(votes), key=votes.count)
            mean_delta = (sum(deltas) / len(deltas)) if deltas else 0.0
            out[module_name] = {
                "dominant_vote": dominant_vote,
                "mean_delta": round(mean_delta, 6),
                "payload_keys": sorted(entry.get("payload_keys", set())),
                "reason_examples": sorted(entry.get("reason_examples", set())),
            }
        return out

    def _build_existing_module_purpose(
        self,
        module_name: str,
        truth_class: str,
        truth_rationale: str,
        stats: dict[str, Any],
        behavior: dict[str, Any],
        context: dict[str, Any],
    ) -> str:
        avg_delta = float(stats.get("avg_confidence_delta", 0.0))
        samples = int(stats.get("samples", 0))
        dominant_vote = str(behavior.get("dominant_vote", "neutral"))
        mean_delta = float(behavior.get("mean_delta", 0.0))
        payload_keys = ",".join(behavior.get("payload_keys", [])[:4]) or "none"

        return (
            f"Existing module {module_name} classified as {truth_class}; {truth_rationale} "
            f"Observed in replay session={context.get('dominant_session', 'unknown')} regime_proxy={context.get('regime_proxy', 'mixed')} "
            f"with samples={samples}, avg_delta={avg_delta:.3f}, dominant_vote={dominant_vote}, mean_delta={mean_delta:.3f}, "
            f"payload_keys={payload_keys}."
        )

    def _make_decisions(
        self,
        hypotheses: list[dict[str, Any]],
        candidate_specs: list[dict[str, Any]],
        overlap_report: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        overlap_map = {str(item.get("candidate_id", "")): item for item in overlap_report}
        hypothesis_map = {str(item.get("hypothesis_id", "")): item for item in hypotheses}

        decisions: list[dict[str, Any]] = []
        for spec in candidate_specs:
            candidate_id = str(spec.get("candidate_id", "unknown"))
            hypothesis = hypothesis_map.get(str(spec.get("hypothesis_id", "")), {})
            overlap = overlap_map.get(candidate_id, {})
            evidence = hypothesis.get("evidence", {}) if isinstance(hypothesis.get("evidence"), dict) else {}

            clarity = len(str(hypothesis.get("statement", "")).strip()) >= 35
            measurable = bool(evidence)
            no_forbidden_mutation = True

            usefulness, unstable, usefulness_reasons = self._evaluate_usefulness(hypothesis, evidence)
            duplicate_risk = bool(overlap.get("is_duplicate_risk", False))
            merge_candidate = bool(overlap.get("merge_candidate", False))

            gate_results = {
                "hypothesis_clarity": clarity,
                "replay_usefulness": usefulness,
                "non_duplication": not duplicate_risk,
                "measurable_contribution": measurable,
                "no_forbidden_core_mutation": no_forbidden_mutation,
            }

            decision_reasons = list(usefulness_reasons)
            if duplicate_risk:
                decision_reasons.append("duplicate inputs/outputs profile")
            elif merge_candidate:
                decision_reasons.append("merge due to overlapping purpose and truth class")

            if not clarity:
                decision = "REJECT"
                decision_reasons.append("hypothesis statement lacks clarity")
            elif not measurable:
                decision = "REJECT"
                decision_reasons.append("missing measurable evidence")
            elif duplicate_risk:
                decision = "REJECT"
            elif merge_candidate:
                decision = "MERGE"
            elif unstable:
                decision = "HOLD_FOR_MORE_DATA"
                decision_reasons.append("hold due to unstable evidence")
            elif not usefulness:
                decision = "REJECT"
            else:
                decision = "KEEP"
                decision_reasons.append("material contribution and non-duplicate profile")

            decisions.append(
                {
                    "candidate_id": candidate_id,
                    "hypothesis_id": spec.get("hypothesis_id", "unknown"),
                    "decision": decision,
                    "gates": gate_results,
                    "decision_reasons": sorted(set(decision_reasons)),
                    "overlap": overlap,
                }
            )

        return decisions

    def _evaluate_usefulness(self, hypothesis: dict[str, Any], evidence: dict[str, Any]) -> tuple[bool, bool, list[str]]:
        source = str(hypothesis.get("source", ""))
        scope = str(hypothesis.get("usefulness_scope", "general"))
        reasons: list[str] = []

        if source == "module_contribution_report":
            samples = int(evidence.get("samples", 0))
            alignment_strength = float(evidence.get("alignment_strength", 0.0))
            confidence_impact = abs(float(evidence.get("avg_confidence_delta", 0.0)))
            consistency = float(evidence.get("directional_consistency", 0.0))

            strong = (
                samples >= self.MIN_SAMPLES_KEEP
                and alignment_strength >= self.MIN_ALIGNMENT_KEEP
                and confidence_impact >= self.MIN_ABS_DELTA_KEEP
                and consistency >= self.MIN_CONSISTENCY_KEEP
            )
            partial = (
                samples >= self.MIN_SAMPLES_HOLD
                and alignment_strength >= self.MIN_ALIGNMENT_HOLD
                and confidence_impact >= self.MIN_ABS_DELTA_HOLD
                and consistency >= self.MIN_CONSISTENCY_HOLD
            )

            regime_specific = evidence.get("regime_specific_alignment", {})
            regime_specific_ratio = (
                float(regime_specific.get("ratio", 0.0)) if isinstance(regime_specific, dict) else 0.0
            )
            blocker_protection_strength = float(evidence.get("blocker_protection_strength", 0.0))
            confidence_calibration_shift = abs(float(evidence.get("confidence_calibration_shift", 0.0)))

            enrichment_score = 0
            if regime_specific_ratio >= 0.5:
                enrichment_score += 1
            if blocker_protection_strength >= 0.3:
                enrichment_score += 1
            if confidence_calibration_shift >= 0.02:
                enrichment_score += 1

            if not strong and not partial:
                reasons.extend(
                    [
                        "insufficient sample support",
                        "insufficient directional alignment",
                        "weak contribution delta",
                    ]
                )
                return False, False, reasons

            if partial and not strong:
                if enrichment_score >= 2:
                    reasons.append("replay evidence enrichment raised usefulness confidence")
                    if scope == "conditional":
                        reasons.append("conditional usefulness supported for current context")
                    else:
                        reasons.append("general usefulness supported across replay context")
                    return True, False, reasons
                reasons.extend(
                    [
                        "evidence partially sufficient",
                        "hold due to unstable evidence",
                    ]
                )
                return False, True, reasons

            if enrichment_score >= 1:
                reasons.append("replay evidence enrichment supports usefulness")
            if scope == "conditional":
                reasons.append("conditional usefulness supported for current context")
            else:
                reasons.append("general usefulness supported across replay context")
            return True, False, reasons

        if source == "blocker_effect_report":
            reason_count = int(evidence.get("count", 0))
            protective_ratio = float(evidence.get("protective_ratio", 0.0))

            strong = (
                reason_count >= self.MIN_BLOCKER_COUNT_KEEP
                and protective_ratio >= self.MIN_PROTECTIVE_RATIO_KEEP
            )
            partial = (
                reason_count >= self.MIN_BLOCKER_COUNT_HOLD
                and protective_ratio >= self.MIN_PROTECTIVE_RATIO_HOLD
            )

            if not strong and not partial:
                reasons.extend(
                    [
                        "blocker-protective association too weak",
                        "insufficient sample support",
                    ]
                )
                return False, False, reasons
            if partial and not strong:
                reasons.extend(["blocker signal emerging", "hold due to unstable evidence"])
                return False, True, reasons

            reasons.append("conditional usefulness supported for failure context")
            return True, False, reasons

        if source == "session_report":
            total = int(evidence.get("total", 0))
            block_rate = float(evidence.get("block_rate", 0.0))
            if total < self.MIN_SAMPLES_HOLD:
                reasons.extend(["insufficient sample support", "hold due to unstable evidence"])
                return False, True, reasons
            if block_rate < 0.3:
                reasons.append("weak contribution delta")
                return False, False, reasons
            reasons.append("conditional usefulness supported for timing context")
            return True, False, reasons

        reasons.append("unsupported hypothesis source")
        return False, False, reasons

    def _normalize_action_alignment(self, stats: dict[str, Any]) -> dict[str, Any]:
        raw = stats.get("action_alignment")
        if isinstance(raw, dict):
            aligned = int(raw.get("aligned", 0))
            misaligned = int(raw.get("misaligned", 0))
            wait_aligned = int(raw.get("wait_aligned", 0))
            ratio = float(raw.get("alignment_ratio", 0.0))
            count_wait = bool(raw.get("count_wait_alignment", False))
            return {
                "aligned": aligned,
                "misaligned": misaligned,
                "wait_aligned": wait_aligned,
                "alignment_ratio": ratio,
                "count_wait_alignment": count_wait,
            }

        # Legacy fallback should evaluate as non-aligned evidence, not action frequency.
        samples = int(stats.get("samples", 0))
        return {
            "aligned": 0,
            "misaligned": samples,
            "wait_aligned": 0,
            "alignment_ratio": 0.0,
            "count_wait_alignment": False,
        }

    def _direction_consistency(self, stats: dict[str, Any], samples: int) -> float:
        if samples <= 0:
            return 0.0
        directional_votes = max(
            int(stats.get("buy_votes", 0)),
            int(stats.get("sell_votes", 0)),
            int(stats.get("wait_votes", 0)),
        )
        return directional_votes / samples

    def _prioritize_hypotheses(self, hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def score(item: dict[str, Any]) -> float:
            evidence = item.get("evidence", {}) if isinstance(item.get("evidence"), dict) else {}
            source = str(item.get("source", ""))
            if source == "module_contribution_report":
                return (
                    float(evidence.get("alignment_strength", 0.0))
                    + abs(float(evidence.get("avg_confidence_delta", 0.0)))
                    + float(evidence.get("directional_consistency", 0.0))
                )
            if source == "blocker_effect_report":
                return float(evidence.get("protective_ratio", 0.0)) + (float(evidence.get("count", 0)) / 10.0)
            if source == "session_report":
                return float(evidence.get("block_rate", 0.0)) + (float(evidence.get("total", 0)) / 20.0)
            return 0.0

        sorted_items = sorted(hypotheses, key=score, reverse=True)
        picked: list[dict[str, Any]] = []

        for source in ("blocker_effect_report", "module_contribution_report", "session_report"):
            for item in sorted_items:
                if str(item.get("source", "")) == source and item not in picked:
                    picked.append(item)
                    break

        for item in sorted_items:
            if item in picked:
                continue
            picked.append(item)

        return picked

    def _write_artifacts(
        self,
        hypotheses: list[dict[str, Any]],
        candidate_specs: list[dict[str, Any]],
        overlap_report: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
        summary: dict[str, Any],
        validated_knowledge_registry_path: Path,
    ) -> dict[str, str]:
        stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d%H%M%S")
        candidates_path = self.root / f"candidate_module_specs.{stamp}.json"
        overlap_path = self.root / f"overlap_scoring.{stamp}.json"
        ledger_path = self.root / f"governance_ledger.{stamp}.json"
        summary_path = self.root / f"governance_summary.{stamp}.json"
        sandbox_candidates_path = self.root / f"sandbox_candidates.{stamp}.json"

        write_json_atomic(candidates_path, {"generated_at": stamp, "candidates": candidate_specs})
        write_json_atomic(overlap_path, {"generated_at": stamp, "overlap": overlap_report})
        write_json_atomic(
            ledger_path,
            {
                "generated_at": stamp,
                "hypotheses": hypotheses,
                "decisions": decisions,
            },
        )
        write_json_atomic(summary_path, {"generated_at": stamp, "summary": summary})
        hypothesis_by_id = {str(item.get("hypothesis_id", "")): item for item in hypotheses}
        sandbox_candidates = []
        for spec in candidate_specs:
            candidate_id = str(spec.get("candidate_id", ""))
            decision = next((d for d in decisions if str(d.get("candidate_id", "")) == candidate_id), {})
            if str(decision.get("decision", "")) == "REJECT":
                continue
            hypothesis = hypothesis_by_id.get(str(spec.get("hypothesis_id", "")), {})
            sandbox_candidates.append(
                {
                    "candidate_id": candidate_id,
                    "hypothesis_id": spec.get("hypothesis_id", ""),
                    "decision": decision.get("decision", "HOLD_FOR_MORE_DATA"),
                    "truth_class": spec.get("truth_class", "meta-intelligence"),
                    "candidate_spec": spec.get("spec", {}),
                    "evidence_history": hypothesis.get("evidence_history", []),
                }
            )
        write_json_atomic(
            sandbox_candidates_path,
            {
                "generated_at": stamp,
                "sandbox_candidates": sandbox_candidates,
            },
        )

        return {
            "hypothesis_registry": str(self.registry.path),
            "candidate_specs": str(candidates_path),
            "overlap_report": str(overlap_path),
            "governance_ledger": str(ledger_path),
            "governance_summary": str(summary_path),
            "sandbox_candidates": str(sandbox_candidates_path),
            "validated_knowledge_registry": str(validated_knowledge_registry_path),
        }

    def _persist_validated_knowledge_registry(
        self,
        hypotheses: list[dict[str, Any]],
        candidate_specs: list[dict[str, Any]],
        decisions: list[dict[str, Any]],
    ) -> Path:
        path = self.root / "validated_knowledge_registry.json"
        payload = read_json_safe(path, default={"validated_knowledge": []})
        if not isinstance(payload, dict):
            payload = {"validated_knowledge": []}

        existing_items = payload.get("validated_knowledge", [])
        if not isinstance(existing_items, list):
            existing_items = []

        existing_by_hypothesis = {
            str(item.get("hypothesis_id", "")): item for item in existing_items if isinstance(item, dict)
        }
        hypothesis_map = {str(item.get("hypothesis_id", "")): item for item in hypotheses}
        candidate_map = {str(item.get("candidate_id", "")): item for item in candidate_specs}

        for decision in decisions:
            if str(decision.get("decision", "")) not in {"KEEP", "MERGE"}:
                continue

            candidate_id = str(decision.get("candidate_id", ""))
            hypothesis_id = str(decision.get("hypothesis_id", ""))
            hypothesis = hypothesis_map.get(hypothesis_id, {})
            candidate = candidate_map.get(candidate_id, {})

            evidence_history = (
                list(hypothesis.get("evidence_history", []))
                if isinstance(hypothesis.get("evidence_history"), list)
                else []
            )
            if not evidence_history and hypothesis.get("evidence", {}):
                evidence_history = [hypothesis.get("evidence", {})]
            overlap_info = decision.get("overlap", {})
            if not isinstance(overlap_info, dict):
                overlap_info = {}

            entry = {
                "hypothesis_id": hypothesis_id,
                "candidate_id": candidate_id,
                "decision": decision.get("decision", ""),
                "truth_class": hypothesis.get("truth_class", candidate.get("truth_class", "meta-intelligence")),
                "statement": hypothesis.get("statement", ""),
                "decision_reasons": decision.get("decision_reasons", []),
                "overlap_score": overlap_info.get("overlap_score", 0.0),
                "evidence_history": evidence_history,
                "updated_at": datetime.now(tz=timezone.utc).isoformat(),
            }
            existing_by_hypothesis[hypothesis_id] = entry

        payload["validated_knowledge"] = sorted(existing_by_hypothesis.values(), key=lambda item: str(item.get("hypothesis_id", "")))
        payload["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        write_json_atomic(path, payload)
        return path


def run_knowledge_expansion_phase_a(
    replay_report: dict[str, Any],
    root: Path,
    candidate_limit: int = 6,
) -> dict[str, Any]:
    orchestrator = KnowledgeExpansionOrchestrator(root=root, candidate_limit=candidate_limit)
    return orchestrator.run(replay_report)
