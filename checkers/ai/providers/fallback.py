from __future__ import annotations

from checkers.ai.contracts import CheckersAIMoveProvider
from checkers.ai.models import (
    CheckersAIMoveContext,
    CheckersAIProviderError,
    CheckersAIProviderResult,
    CheckersAIProviderUnavailableError,
)


class CheckersFallbackProvider(CheckersAIMoveProvider):
    def __init__(self, providers: tuple[CheckersAIMoveProvider, ...]):
        if not providers:
            raise ValueError("CheckersFallbackProvider requires at least one provider")
        self._providers = providers
        names = ",".join(provider.provider_name for provider in providers)
        self.provider_name = f"checkers-fallback:{names}"

    def choose_move(self, context: CheckersAIMoveContext) -> CheckersAIProviderResult:
        failures: list[str] = []

        for provider in self._providers:
            try:
                result = provider.choose_move(context)
                return result
            except CheckersAIProviderError as error:
                failures.append(str(error))
            except Exception as error:
                failures.append(f"[{provider.provider_name}] {error}")

        message = "All providers failed"
        if failures:
            message = f"{message}: {'; '.join(failures)}"
        raise CheckersAIProviderUnavailableError(self.provider_name, message)
