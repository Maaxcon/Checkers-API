from checkers.ai.models import (
    CheckersAIMoveContext,
    CheckersAIMoveDecision,
    CheckersAIProviderIllegalMoveError,
)


def validate_checkers_ai_decision_is_legal(
    provider_name: str,
    context: CheckersAIMoveContext,
    decision: CheckersAIMoveDecision,
) -> None:
    if decision in context.legal_moves:
        return

    raise CheckersAIProviderIllegalMoveError(
        provider_name,
        (
            "Model returned illegal move: "
            f"from=({decision.from_row},{decision.from_col}) "
            f"to=({decision.to_row},{decision.to_col})"
        ),
    )
