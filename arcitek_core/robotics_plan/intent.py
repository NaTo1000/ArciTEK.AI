"""Human-intent alignment and predictive-error decision support.

The engine is deliberately deterministic: callers provide structured evidence
about candidate moves, and the engine ranks that evidence against an immutable
intent profile. It never executes a move and never replaces human approval.
"""

from __future__ import annotations

import statistics
from typing import Any

from .knowledge import KnowledgeRepository
from .validation import (
    MAX_LIST_ITEMS,
    MAX_NAME_LENGTH,
    MAX_TEXT_LENGTH,
    ValidationError,
    validate_dict,
    validate_identifier,
    validate_list,
    validate_number,
    validate_string,
)

BUILT_IN_GUARDRAILS = (
    "Require explicit human approval before release",
    "Do not execute caller-supplied code or commands",
    "Preserve immutable revision and audit history",
)
MAX_CANDIDATES = 50


def _string_list(value: Any, field: str, *, max_items: int = MAX_LIST_ITEMS) -> list[str]:
    return [
        validate_string(item, f"{field}[{index}]", max_len=MAX_TEXT_LENGTH)
        for index, item in enumerate(validate_list(value, field, max_items=max_items))
    ]


class IntentAlignmentEngine:
    """Stores HIAI profiles and ranks moves with a bounded PECS score."""

    def __init__(self, knowledge: KnowledgeRepository) -> None:
        self.knowledge = knowledge

    def capture_intent(
        self,
        *,
        project_id: str,
        actor: str,
        reason: str,
        goal: str,
        success_criteria: list[str],
        constraints: list[str] | None = None,
        guardrails: list[str] | None = None,
        out_of_scope: list[str] | None = None,
    ) -> dict[str, Any]:
        project_id = validate_identifier(project_id, "project_id")
        actor = validate_string(actor, "actor", max_len=MAX_NAME_LENGTH)
        reason = validate_string(reason, "reason", max_len=MAX_TEXT_LENGTH)
        goal = validate_string(goal, "goal", max_len=MAX_TEXT_LENGTH)
        criteria = _string_list(success_criteria, "success_criteria")
        if not criteria:
            raise ValidationError("success_criteria must contain at least one item")
        previous = self.get_active_intent(project_id, required=False)
        custom_guardrails = (
            list(previous["custom_guardrails"])
            if guardrails is None and previous is not None
            else _string_list(guardrails, "guardrails")
        )
        effective_guardrails = list(BUILT_IN_GUARDRAILS)
        effective_guardrails.extend(
            item for item in custom_guardrails if item not in effective_guardrails
        )
        record = self.knowledge.append_record(
            project_id=project_id,
            actor=actor,
            reason=reason,
            record_type="intent_profile",
            content={
                "goal": goal,
                "success_criteria": criteria,
                "constraints": _string_list(constraints, "constraints"),
                "guardrails": effective_guardrails,
                "custom_guardrails": custom_guardrails,
                "out_of_scope": _string_list(out_of_scope, "out_of_scope"),
            },
            parent_id=previous["id"] if previous else None,
            supersedes_id=previous["id"] if previous else None,
            confidence=1.0,
            tags=["hiai", "intent", "guardrails"],
        )
        return self._profile(record)

    def get_active_intent(
        self, project_id: str, *, required: bool = True
    ) -> dict[str, Any] | None:
        project_id = validate_identifier(project_id, "project_id")
        records = self.knowledge.timeline(
            project_id, record_type="intent_profile", limit=1_000
        )
        if not records:
            if required:
                raise ValidationError("No intent profile exists for this project")
            return None
        return self._profile(records[-1])

    def list_intents(self, project_id: str) -> list[dict[str, Any]]:
        project_id = validate_identifier(project_id, "project_id")
        return [
            self._profile(record)
            for record in self.knowledge.timeline(
                project_id, record_type="intent_profile", limit=1_000
            )
        ]

    def evaluate_moves(
        self,
        *,
        project_id: str,
        actor: str,
        reason: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        actor = validate_string(actor, "actor", max_len=MAX_NAME_LENGTH)
        reason = validate_string(reason, "reason", max_len=MAX_TEXT_LENGTH)
        candidate_items = validate_list(
            candidates, "candidates", max_items=MAX_CANDIDATES
        )
        if not candidate_items:
            raise ValidationError("candidates must contain at least one item")
        profile = self.get_active_intent(project_id)
        calibration_error = self._calibration_error(project_id)
        scored = [
            self._score_candidate(candidate, index, profile, calibration_error)
            for index, candidate in enumerate(candidate_items)
        ]
        candidate_ids = [candidate["id"] for candidate in scored]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValidationError("candidate ids must be unique")
        eligible = [candidate for candidate in scored if not candidate["blocked"]]
        ranked = sorted(
            scored,
            key=lambda candidate: (
                candidate["blocked"],
                -candidate["pecs_score"],
                candidate["predicted_error"],
                candidate["id"],
            ),
        )
        selected = next(
            (candidate for candidate in ranked if not candidate["blocked"]), None
        )
        result = {
            "intent_id": profile["id"],
            "intent_goal": profile["goal"],
            "calibration_error": calibration_error,
            "selected_candidate_id": selected["id"] if selected else None,
            "status": "candidate_selected" if selected else "blocked",
            "drift_detected": selected["drift_detected"] if selected else True,
            "requires_human_review": True,
            "candidates": ranked,
        }
        record = self.knowledge.append_record(
            project_id=project_id,
            actor=actor,
            reason=reason,
            record_type="pecs_evaluation",
            content=result,
            parent_id=profile["id"],
            confidence=selected["confidence"] if selected else 0.0,
            tags=["hiai", "pecs", "decision"],
        )
        return {"id": record["id"], **result}

    def record_outcome(
        self,
        *,
        project_id: str,
        actor: str,
        reason: str,
        evaluation_id: str,
        actual_error: float,
        notes: str = "",
    ) -> dict[str, Any]:
        evaluation_id = validate_identifier(evaluation_id, "evaluation_id")
        evaluation = self.knowledge.get_record(evaluation_id)
        if (
            evaluation["project_id"] != validate_identifier(project_id, "project_id")
            or evaluation["record_type"] != "pecs_evaluation"
        ):
            raise ValidationError(
                "evaluation_id must reference a PECS evaluation in the same project"
            )
        selected_id = evaluation["content"].get("selected_candidate_id")
        if selected_id is None:
            raise ValidationError("Cannot record an outcome for a blocked evaluation")
        selected = next(
            item
            for item in evaluation["content"]["candidates"]
            if item["id"] == selected_id
        )
        actual_error = validate_number(
            actual_error, "actual_error", minimum=0, maximum=1
        )
        record = self.knowledge.append_record(
            project_id=project_id,
            actor=validate_string(actor, "actor", max_len=MAX_NAME_LENGTH),
            reason=validate_string(reason, "reason", max_len=MAX_TEXT_LENGTH),
            record_type="pecs_outcome",
            content={
                "evaluation_id": evaluation_id,
                "candidate_id": selected_id,
                "predicted_error": selected["predicted_error"],
                "actual_error": actual_error,
                "prediction_delta": round(
                    actual_error - selected["predicted_error"], 6
                ),
                "notes": validate_string(
                    notes,
                    "notes",
                    max_len=MAX_TEXT_LENGTH,
                    allow_empty=True,
                    default="",
                ),
            },
            parent_id=evaluation_id,
            confidence=1.0,
            tags=["hiai", "pecs", "feedback"],
        )
        return record

    def _score_candidate(
        self,
        candidate: Any,
        index: int,
        profile: dict[str, Any],
        calibration_error: float,
    ) -> dict[str, Any]:
        item = validate_dict(candidate, f"candidates[{index}]")
        candidate_id = validate_identifier(
            item.get("id"), f"candidates[{index}].id"
        )
        description = validate_string(
            item.get("description"),
            f"candidates[{index}].description",
            max_len=MAX_TEXT_LENGTH,
        )
        satisfies = _string_list(
            item.get("satisfies"), f"candidates[{index}].satisfies"
        )
        criterion_set = set(profile["success_criteria"])
        unknown_criteria = sorted(set(satisfies) - criterion_set)
        covered = criterion_set.intersection(satisfies)
        constraint_violations = _string_list(
            item.get("constraint_violations"),
            f"candidates[{index}].constraint_violations",
        )
        guardrail_violations = _string_list(
            item.get("guardrail_violations"),
            f"candidates[{index}].guardrail_violations",
        )
        confidence = validate_number(
            item.get("confidence", 0.5),
            f"candidates[{index}].confidence",
            minimum=0,
            maximum=0.95,
        )
        predicted_error = validate_number(
            item.get("predicted_error", 0.5),
            f"candidates[{index}].predicted_error",
            minimum=0,
            maximum=1,
        )
        adjusted_error = min(1.0, predicted_error + calibration_error)
        coverage = len(covered) / len(criterion_set)
        blocked_reasons = [
            *(f"constraint: {value}" for value in constraint_violations),
            *(f"guardrail: {value}" for value in guardrail_violations),
        ]
        if unknown_criteria:
            blocked_reasons.append(
                "unknown success criteria: " + ", ".join(unknown_criteria)
            )
        blocked = bool(blocked_reasons)
        score = 0.0 if blocked else 0.55 * coverage + 0.25 * confidence + 0.2 * (
            1 - adjusted_error
        )
        return {
            "id": candidate_id,
            "description": description,
            "pecs_score": round(score, 6),
            "criteria_coverage": round(coverage, 6),
            "confidence": confidence,
            "predicted_error": predicted_error,
            "adjusted_error": round(adjusted_error, 6),
            "blocked": blocked,
            "blocked_reasons": blocked_reasons,
            "drift_detected": blocked or coverage < 1.0,
            "unmet_criteria": sorted(criterion_set - covered),
        }

    def _calibration_error(self, project_id: str) -> float:
        outcomes = self.knowledge.timeline(
            project_id, record_type="pecs_outcome", limit=200
        )
        if not outcomes:
            return 0.0
        absolute_errors = [
            abs(
                record["content"]["actual_error"]
                - record["content"]["predicted_error"]
            )
            for record in outcomes
        ]
        return round(min(0.5, statistics.fmean(absolute_errors)), 6)

    @staticmethod
    def _profile(record: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": record["id"],
            "project_id": record["project_id"],
            "actor": record["actor"],
            "reason": record["reason"],
            "created_at": record["created_at"],
            **record["content"],
        }
