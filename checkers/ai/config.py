from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckersOpenRouterConfig:
    api_key: str
    models: tuple[str, ...]
    timeout_ms: int
    max_retries: int


def load_checkers_openrouter_config() -> CheckersOpenRouterConfig:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required")

    models = _parse_models(os.getenv("AI_OPENROUTER_MODELS", ""))
    if not models:
        raise ValueError("AI_OPENROUTER_MODELS must contain at least one model")

    timeout_ms = _parse_int("AI_TIMEOUT_MS", default=8000, minimum=1)
    max_retries = _parse_int("AI_MAX_RETRIES", default=2, minimum=0)

    return CheckersOpenRouterConfig(
        api_key=api_key,
        models=models,
        timeout_ms=timeout_ms,
        max_retries=max_retries,
    )


def _parse_models(raw_value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw_value.split(",") if part.strip())


def _parse_int(name: str, default: int, minimum: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or not raw_value.strip():
        return default

    try:
        value = int(raw_value.strip())
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error

    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value
