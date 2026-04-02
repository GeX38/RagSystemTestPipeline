from __future__ import annotations

from pathlib import Path
from typing import Any

from .methodology_common import load_json_payload


CLINICAL_METHODOLOGY_METHOD_KEY = "clinical_methodology_v1"
DEFAULT_CLINICAL_METHODOLOGY_METRICS_PATH = Path(__file__).resolve().parent / "clinical_methodology_metrics.json"


def load_clinical_methodology_metrics(path: str | Path | None = None) -> dict[str, Any]:
    payload = load_json_payload(path or DEFAULT_CLINICAL_METHODOLOGY_METRICS_PATH)
    if not isinstance(payload, dict):
        raise ValueError("Expected a top-level object in clinical_methodology_metrics.json")
    return payload


__all__ = [
    "CLINICAL_METHODOLOGY_METHOD_KEY",
    "DEFAULT_CLINICAL_METHODOLOGY_METRICS_PATH",
    "load_clinical_methodology_metrics",
]
