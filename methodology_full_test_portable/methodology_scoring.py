from __future__ import annotations

import json
import math
import re
from typing import Any

from .methodology_common import normalize_text


JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def extract_json_payload(text: str) -> dict[str, Any]:
    raw_text = str(text or "").strip()
    if not raw_text:
        raise ValueError("Judge returned an empty response")

    fenced_match = JSON_BLOCK_RE.search(raw_text)
    candidate = fenced_match.group(1) if fenced_match else raw_text

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start >= 0 and end > start:
        candidate = candidate[start : end + 1]

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse judge JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Judge response is not a JSON object")
    return payload


def _criteria_index(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id") or "").strip(): item
        for item in items
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }


def _coerce_binary_score(value: Any) -> int:
    try:
        return 1 if int(value) > 0 else 0
    except (TypeError, ValueError):
        return 0


def summarize_methodology_verdict(
    verdict: dict[str, Any],
    *,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    blocking_payload = _criteria_index(list(verdict.get("blocking_criteria") or []))
    blocking_reports: list[dict[str, Any]] = []
    blocking_failed = False
    for criterion in metrics.get("blocking_criteria", []):
        if not isinstance(criterion, dict):
            continue
        criterion_id = str(criterion.get("id") or "").strip()
        reported = blocking_payload.get(criterion_id, {})
        score = _coerce_binary_score(reported.get("score"))
        if score == 0:
            blocking_failed = True
        blocking_reports.append(
            {
                "id": criterion_id,
                "label": criterion.get("label"),
                "score": score,
                "reason": normalize_text(reported.get("reason")),
            }
        )

    domain_payload = _criteria_index(list(verdict.get("domains") or []))
    domain_reports: list[dict[str, Any]] = []
    domain_scores: list[float] = []
    for domain in metrics.get("domains", []):
        if not isinstance(domain, dict):
            continue
        domain_id = str(domain.get("id") or "").strip()
        reported_domain = domain_payload.get(domain_id, {})
        reported_criteria = _criteria_index(list(reported_domain.get("criteria") or []))

        criteria_reports: list[dict[str, Any]] = []
        positive_count = 0
        total_criteria = 0
        for criterion in domain.get("criteria", []):
            if not isinstance(criterion, dict):
                continue
            total_criteria += 1
            criterion_id = str(criterion.get("id") or "").strip()
            reported = reported_criteria.get(criterion_id, {})
            score = _coerce_binary_score(reported.get("score"))
            positive_count += score
            criteria_reports.append(
                {
                    "id": criterion_id,
                    "label": criterion.get("label"),
                    "score": score,
                    "reason": normalize_text(reported.get("reason")),
                }
            )

        normalized_score = positive_count / max(1, total_criteria)
        domain_scores.append(normalized_score)
        domain_reports.append(
            {
                "id": domain_id,
                "label": domain.get("label"),
                "positive_count": positive_count,
                "total_criteria": total_criteria,
                "normalized_score": round(normalized_score, 4),
                "criteria": criteria_reports,
                "summary": normalize_text(reported_domain.get("summary")),
            }
        )

    okl_score = math.prod(domain_scores) if domain_scores else 0.0
    if blocking_failed:
        judge_class = "C"
    elif okl_score >= float(metrics.get("classification", {}).get("A", {}).get("min_okl", 0.8)):
        judge_class = "A"
    elif okl_score >= float(metrics.get("classification", {}).get("B", {}).get("min_okl", 0.6)):
        judge_class = "B"
    else:
        judge_class = "C"

    return {
        "okl_score": round(okl_score, 4),
        "judge_class": judge_class,
        "blocking_failed": blocking_failed,
        "blocking_criteria": blocking_reports,
        "domains": domain_reports,
        "judge_summary": normalize_text(verdict.get("judge_summary")),
        "raw_verdict": verdict,
    }


__all__ = [
    "extract_json_payload",
    "summarize_methodology_verdict",
]
