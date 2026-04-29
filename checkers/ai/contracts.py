from typing import Protocol, runtime_checkable

from checkers.ai.models import CheckersAIMoveContext, CheckersAIProviderResult


@runtime_checkable
class CheckersAIMoveProvider(Protocol):
    provider_name: str

    def choose_move(self, context: CheckersAIMoveContext) -> CheckersAIProviderResult:
        ...
