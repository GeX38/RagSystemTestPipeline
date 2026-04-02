from __future__ import annotations

from typing import Any, Callable

from .client_protocol import JudgeModelProtocol
from .methodology_common import normalize_text
from .methodology_prompting import (
    build_methodology_blocking_prompt,
    build_methodology_domain_prompt,
)
from .methodology_scoring import extract_json_payload


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


async def _run_json_judge(
    *,
    judge_client: JudgeModelProtocol,
    base_prompt: str,
    judge_temperature: float,
    expected_ids: list[str],
    extract_ids: Callable[[dict[str, Any]], list[str]],
) -> dict[str, Any]:
    prompt = base_prompt
    last_payload: dict[str, Any] | None = None

    for _ in range(2):
        raw_text = await judge_client.complete(
            prompt=prompt,
            temperature=judge_temperature,
            max_tokens=1600,
        )
        payload = extract_json_payload(raw_text)
        last_payload = payload

        present_ids = {item for item in extract_ids(payload) if item}
        missing_ids = [item for item in expected_ids if item not in present_ids]
        if not missing_ids:
            return payload

        prompt = "\n\n".join(
            [
                base_prompt,
                (
                    "THE PREVIOUS RESPONSE WAS INCOMPLETE. "
                    f"Missing required IDs: {', '.join(missing_ids)}. "
                    "Repeat the evaluation and return the FULL JSON without omitting any required ID."
                ),
            ]
        )

    return last_payload or {}


def _extract_blocking_ids(payload: dict[str, Any]) -> list[str]:
    return [
        str(item.get("id") or "").strip()
        for item in payload.get("blocking_criteria") or []
        if isinstance(item, dict)
    ]


def _extract_domain_ids(payload: dict[str, Any], *, expected_domain_id: str) -> list[str]:
    reported_domain_id = str(payload.get("id") or "").strip()
    if reported_domain_id != expected_domain_id:
        return []
    return [
        str(item.get("id") or "").strip()
        for item in payload.get("criteria") or []
        if isinstance(item, dict)
    ]


def coerce_blocking_verdict(
    payload: dict[str, Any],
    *,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    reported = _criteria_index(list(payload.get("blocking_criteria") or []))
    criteria = []
    for criterion in metrics.get("blocking_criteria", []):
        if not isinstance(criterion, dict):
            continue
        criterion_id = str(criterion.get("id") or "").strip()
        raw_item = reported.get(criterion_id, {})
        reason = normalize_text(raw_item.get("reason")) or "This criterion was not explicitly evaluated by the judge model."
        criteria.append(
            {
                "id": criterion_id,
                "score": _coerce_binary_score(raw_item.get("score")),
                "reason": reason,
            }
        )
    return {
        "blocking_criteria": criteria,
        "summary": normalize_text(payload.get("summary")),
    }


def coerce_domain_verdict(
    payload: dict[str, Any],
    *,
    domain: dict[str, Any],
) -> dict[str, Any]:
    domain_id = str(domain.get("id") or "").strip()
    reported_domain_id = str(payload.get("id") or "").strip()
    criteria_payload = payload.get("criteria") if reported_domain_id == domain_id else []
    reported = _criteria_index(list(criteria_payload or []))
    criteria = []
    for criterion in domain.get("criteria", []):
        if not isinstance(criterion, dict):
            continue
        criterion_id = str(criterion.get("id") or "").strip()
        raw_item = reported.get(criterion_id, {})
        reason = normalize_text(raw_item.get("reason")) or "This criterion was not explicitly evaluated by the judge model."
        criteria.append(
            {
                "id": criterion_id,
                "score": _coerce_binary_score(raw_item.get("score")),
                "reason": reason,
            }
        )
    return {
        "id": domain_id,
        "criteria": criteria,
        "summary": normalize_text(payload.get("summary")),
    }


async def judge_methodology_blocking(
    *,
    judge_client: JudgeModelProtocol,
    case: dict[str, Any],
    trajectory: list[dict[str, Any]],
    metrics: dict[str, Any],
    judge_temperature: float,
) -> dict[str, Any]:
    expected_ids = [
        str(item.get("id") or "").strip()
        for item in metrics.get("blocking_criteria", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]
    payload = await _run_json_judge(
        judge_client=judge_client,
        base_prompt=build_methodology_blocking_prompt(
            case=case,
            trajectory=trajectory,
            metrics=metrics,
        ),
        judge_temperature=judge_temperature,
        expected_ids=expected_ids,
        extract_ids=_extract_blocking_ids,
    )
    return coerce_blocking_verdict(payload, metrics=metrics)


async def judge_methodology_domain(
    *,
    judge_client: JudgeModelProtocol,
    case: dict[str, Any],
    trajectory: list[dict[str, Any]],
    domain: dict[str, Any],
    judge_temperature: float,
) -> dict[str, Any]:
    domain_id = str(domain.get("id") or "").strip()
    expected_ids = [
        str(item.get("id") or "").strip()
        for item in domain.get("criteria", [])
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    ]
    payload = await _run_json_judge(
        judge_client=judge_client,
        base_prompt=build_methodology_domain_prompt(
            case=case,
            trajectory=trajectory,
            domain=domain,
        ),
        judge_temperature=judge_temperature,
        expected_ids=expected_ids,
        extract_ids=lambda raw_payload: _extract_domain_ids(raw_payload, expected_domain_id=domain_id),
    )
    return coerce_domain_verdict(payload, domain=domain)


def build_methodology_composite_verdict(
    *,
    blocking_verdict: dict[str, Any],
    domain_verdicts: list[dict[str, Any]],
) -> dict[str, Any]:
    summary_parts = [
        normalize_text(blocking_verdict.get("summary")),
        *[
            normalize_text(item.get("summary"))
            for item in domain_verdicts
            if isinstance(item, dict) and normalize_text(item.get("summary"))
        ],
    ]
    return {
        "blocking_criteria": list(blocking_verdict.get("blocking_criteria") or []),
        "domains": list(domain_verdicts or []),
        "strengths": [],
        "weaknesses": [],
        "critical_failures": [],
        "judge_summary": " ".join(item for item in summary_parts if item),
    }


__all__ = [
    "build_methodology_composite_verdict",
    "judge_methodology_blocking",
    "judge_methodology_domain",
]
