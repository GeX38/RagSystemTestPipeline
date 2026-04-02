from __future__ import annotations

from typing import Protocol


class JudgeModelProtocol(Protocol):
    async def complete(
        self,
        *,
        prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str: ...


__all__ = ["JudgeModelProtocol"]
