"""Helpers to normalise OpenAI usage metadata."""
from __future__ import annotations

from typing import Any, Dict, Optional


def extract_usage(completion: Any) -> Optional[Dict[str, int | str]]:
    """Return a simplified usage payload from an OpenAI response."""
    usage = getattr(completion, "usage", None)
    if usage is None:
        return None

    prompt_tokens = getattr(usage, "prompt_tokens", None) or 0
    completion_tokens = getattr(usage, "completion_tokens", None) or 0
    total_tokens = getattr(usage, "total_tokens", None) or 0
    model = getattr(completion, "model", "") or "desconocido"

    try:
        prompt_tokens = int(prompt_tokens)
    except (TypeError, ValueError):  # pragma: no cover - defensive conversion
        prompt_tokens = 0
    try:
        completion_tokens = int(completion_tokens)
    except (TypeError, ValueError):  # pragma: no cover - defensive conversion
        completion_tokens = 0
    try:
        total_tokens = int(total_tokens)
    except (TypeError, ValueError):  # pragma: no cover - defensive conversion
        total_tokens = prompt_tokens + completion_tokens

    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
