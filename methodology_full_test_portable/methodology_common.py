from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def load_json_payload(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as file:
        return json.load(file)


__all__ = ["load_json_payload", "normalize_text"]
