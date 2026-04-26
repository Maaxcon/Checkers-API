from __future__ import annotations

from dataclasses import dataclass, field

from checkers.services.types import Board, Player

JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
RawResponse = dict[str, JSONValue]


@dataclass(frozen=True)
class CheckersAIMoveDecision:
    from_row: int
    from_col: int
    to_row: int
    to_col: int


@dataclass
class CheckersAIMoveContext:
    game_id: str
    board: Board
    current_turn: Player
    difficulty: str
    legal_moves: tuple[CheckersAIMoveDecision, ...]


@dataclass
class CheckersAIProviderResult:
    provider: str
    decision: CheckersAIMoveDecision
    raw_response: RawResponse = field(default_factory=dict)


class CheckersAIProviderError(Exception):
    def __init__(self, provider: str, message: str):
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] {message}")


class CheckersAIProviderTimeoutError(CheckersAIProviderError):
    pass


class CheckersAIProviderUnavailableError(CheckersAIProviderError):
    pass


class CheckersAIProviderInvalidResponseError(CheckersAIProviderError):
    pass


class CheckersAIProviderIllegalMoveError(CheckersAIProviderError):
    pass
