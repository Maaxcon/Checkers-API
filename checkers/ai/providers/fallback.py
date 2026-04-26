from __future__ import annotations

from checkers.ai.contracts import AIMoveProvider
from checkers.ai.models import AIMoveContext, ProviderError, ProviderResult, ProviderUnavailableError


class FallbackProvider(AIMoveProvider):
    def __init__(self, providers: tuple[AIMoveProvider, ...]):
        if not providers:
            raise ValueError("FallbackProvider requires at least one provider")
        self._providers = providers
        names = ",".join(provider.provider_name for provider in providers)
        self.provider_name = f"fallback:{names}"

    def choose_move(self, context: AIMoveContext) -> ProviderResult:
        failures: list[str] = []

        for provider in self._providers:
            try:
                return provider.choose_move(context)
            except ProviderError as error:
                failures.append(str(error))
            except Exception as error:
                failures.append(f"[{provider.provider_name}] {error}")

        message = "All providers failed"
        if failures:
            message = f"{message}: {'; '.join(failures)}"
        raise ProviderUnavailableError(self.provider_name, message)
