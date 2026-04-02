from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from .client_protocol import JudgeModelProtocol
from .methodology_common import load_json_payload, normalize_text
from .methodology_fixtures import (
    CLINICAL_METHODOLOGY_METHOD_KEY,
    load_clinical_methodology_metrics,
)
from .methodology_judge import (
    build_methodology_composite_verdict,
    judge_methodology_blocking,
    judge_methodology_domain,
)
from .methodology_scoring import summarize_methodology_verdict


def _normalize_case_payload(raw_case: dict[str, Any]) -> dict[str, Any]:
    case = dict(raw_case or {})
    normalized = {
        "title": normalize_text(case.get("title")) or None,
        "source_reference": normalize_text(case.get("source_reference")) or None,
        "gold_answer_text": normalize_text(case.get("gold_answer_text")),
        "clinical_risk_level": normalize_text(case.get("clinical_risk_level")) or "moderate",
        "critical_points": [
            normalize_text(item)
            for item in list(case.get("critical_points") or [])
            if normalize_text(item)
        ],
        "critical_red_flags": [
            normalize_text(item)
            for item in list(case.get("critical_red_flags") or [])
            if normalize_text(item)
        ],
        "interface_warning_present": bool(case.get("interface_warning_present", True)),
    }
    if not normalized["gold_answer_text"]:
        raise ValueError("case.gold_answer_text must contain a non-empty expert reference answer.")
    return normalized


def _normalize_trajectory(raw_trajectory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(list(raw_trajectory or []), start=1):
        if not isinstance(item, dict):
            continue
        user_input = normalize_text(item.get("user_input"))
        assistant_answer = normalize_text(item.get("assistant_answer"))
        if not user_input or not assistant_answer:
            continue
        normalized.append(
            {
                "stage_index": int(item.get("stage_index") or index),
                "user_input": user_input,
                "assistant_answer": assistant_answer,
                "assistant_message_id": item.get("assistant_message_id"),
                "created_at": item.get("created_at"),
            }
        )
    if len(normalized) < 2:
        raise ValueError(
            "The full canonical methodology test requires a staged-disclosure trajectory with at least two stages."
        )
    return normalized


async def run_full_methodology_test(
    *,
    case_payload: dict[str, Any],
    trajectory: list[dict[str, Any]],
    judge_client: JudgeModelProtocol,
    judge_temperature: float = 0.0,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metrics_payload = metrics or load_clinical_methodology_metrics()
    normalized_case = _normalize_case_payload(case_payload)
    normalized_trajectory = _normalize_trajectory(trajectory)

    blocking_verdict = await judge_methodology_blocking(
        judge_client=judge_client,
        case=normalized_case,
        trajectory=normalized_trajectory,
        metrics=metrics_payload,
        judge_temperature=float(judge_temperature or 0.0),
    )
    domain_verdicts: list[dict[str, Any]] = []
    for domain in metrics_payload.get("domains", []):
        if not isinstance(domain, dict):
            continue
        domain_verdicts.append(
            await judge_methodology_domain(
                judge_client=judge_client,
                case=normalized_case,
                trajectory=normalized_trajectory,
                domain=domain,
                judge_temperature=float(judge_temperature or 0.0),
            )
        )

    verdict = build_methodology_composite_verdict(
        blocking_verdict=blocking_verdict,
        domain_verdicts=domain_verdicts,
    )
    summary = summarize_methodology_verdict(verdict, metrics=metrics_payload)
    return {
        "method_key": CLINICAL_METHODOLOGY_METHOD_KEY,
        "method_version": int(metrics_payload.get("version", 1) or 1),
        "judge_temperature": float(judge_temperature or 0.0),
        "case_payload": normalized_case,
        "trajectory": normalized_trajectory,
        "verdict": verdict,
        "summary": summary,
    }


def _resolve_input_payload(input_path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = load_json_payload(input_path)
    if not isinstance(payload, dict):
        raise ValueError("Expected a top-level JSON object.")
    case_payload = payload.get("case")
    trajectory = payload.get("trajectory")
    if not isinstance(case_payload, dict):
        raise ValueError("Input JSON must contain a 'case' object.")
    if not isinstance(trajectory, list):
        raise ValueError("Input JSON must contain a 'trajectory' array.")
    return case_payload, trajectory


async def _run_cli(args: argparse.Namespace) -> int:
    case_payload, trajectory = _resolve_input_payload(args.input)

    if args.backend != "dummy":
        raise SystemExit(
            "The standalone CLI is not bound to any specific model provider. "
            "Use the importable run_full_methodology_test(...) function "
            "or add your own judge-client adapter."
        )

    class DummyJudgeClient:
        async def complete(self, *, prompt: str, temperature: float, max_tokens: int) -> str:
            raise RuntimeError(
                "The dummy backend does not perform a real evaluation. "
                "Attach your own judge client through the Python API."
            )

    result = await run_full_methodology_test(
        case_payload=case_payload,
        trajectory=trajectory,
        judge_client=DummyJudgeClient(),
        judge_temperature=float(args.temperature or 0.0),
    )
    output_text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output_text + "\n", encoding="utf-8")
    else:
        print(output_text)
    return 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Standalone pipeline for the full canonical clinical methodology test.",
    )
    parser.add_argument("--input", required=True, help="Path to the input JSON file containing case and trajectory.")
    parser.add_argument("--output", required=False, help="Optional path for saving the resulting JSON.")
    parser.add_argument("--temperature", type=float, default=0.0, help="Judge model temperature.")
    parser.add_argument(
        "--backend",
        default="dummy",
        help="Defaults to dummy. Attach a real judge client through the Python API for actual runs.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return asyncio.run(_run_cli(args))


if __name__ == "__main__":
    raise SystemExit(main())
