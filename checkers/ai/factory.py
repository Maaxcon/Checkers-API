from __future__ import annotations

from checkers.ai.adapters import CheckersOpenRouterHTTPAdapter
from checkers.ai.config import CheckersOpenRouterConfig, load_checkers_openrouter_config
from checkers.ai.contracts import CheckersAIMoveProvider
from checkers.ai.providers import CheckersFallbackProvider, CheckersOpenRouterProvider


def build_checkers_openrouter_provider_chain(
    config: CheckersOpenRouterConfig | None = None,
) -> CheckersAIMoveProvider:
    effective_config = config or load_checkers_openrouter_config()
    adapter = CheckersOpenRouterHTTPAdapter(
        api_key=effective_config.api_key,
        timeout_ms=effective_config.timeout_ms,
    )
    providers = tuple(
        CheckersOpenRouterProvider(
            model_name=model_name,
            adapter=adapter,
            max_retries=effective_config.max_retries,
        )
        for model_name in effective_config.models
    )
    return CheckersFallbackProvider(providers)
