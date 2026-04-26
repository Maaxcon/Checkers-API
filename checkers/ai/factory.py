from __future__ import annotations

from checkers.ai.adapters import CheckersOpenRouterHTTPAdapter
from checkers.ai.config import CheckersOpenRouterConfig, load_checkers_openrouter_config
from checkers.ai.contracts import CheckersAIMoveProvider
from checkers.ai.providers import (
    CheckersFallbackProvider,
    CheckersOpenRouterProvider,
    CheckersRandomProvider,
)


def build_checkers_openrouter_provider_chain(
    config: CheckersOpenRouterConfig | None = None,
) -> CheckersAIMoveProvider:
    providers: list[CheckersAIMoveProvider] = []

    effective_config = config
    if effective_config is None:
        try:
            effective_config = load_checkers_openrouter_config()
        except ValueError:
            effective_config = None

    if effective_config is not None:
        adapter = CheckersOpenRouterHTTPAdapter(
            api_key=effective_config.api_key,
            timeout_ms=effective_config.timeout_ms,
        )
        providers.extend(
            CheckersOpenRouterProvider(
                model_name=model_name,
                adapter=adapter,
                max_retries=effective_config.max_retries,
            )
            for model_name in effective_config.models
        )

    providers.append(CheckersRandomProvider())
    return CheckersFallbackProvider(tuple(providers))
