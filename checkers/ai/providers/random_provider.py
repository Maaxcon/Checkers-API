from __future__ import annotations

import random

from checkers.ai.contracts import CheckersAIMoveProvider
from checkers.ai.models import (
    CheckersAIMoveContext,
    CheckersAIProviderResult,
    CheckersAIProviderUnavailableError,
)


class CheckersRandomProvider(CheckersAIMoveProvider):
    def __init__(self) -> None:
        self.provider_name = "checkers-random"

    def choose_move(self, context: CheckersAIMoveContext) -> CheckersAIProviderResult:
        if not context.legal_moves:
            raise CheckersAIProviderUnavailableError(self.provider_name, "No legal moves available")

        decision = random.choice(context.legal_moves)
        return CheckersAIProviderResult(
            provider=self.provider_name,
            decision=decision,
        )
