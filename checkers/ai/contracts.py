from typing import Protocol, runtime_checkable

from checkers.ai.models import AIMoveContext, ProviderResult


@runtime_checkable
class AIMoveProvider(Protocol):
    provider_name: str

    def choose_move(self, context: AIMoveContext) -> ProviderResult:
        ...
