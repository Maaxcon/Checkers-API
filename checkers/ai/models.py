from __future__ import annotations

from dataclasses import dataclass, field

from checkers.services.types import Board, Player

JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


@dataclass(frozen=True)
class AIMoveDecision:
    from_row: int
    from_col: int
    to_row: int
    to_col: int


@dataclass
class AIMoveContext:
    game_id: str
    board: Board
    current_turn: Player
    difficulty: str
    legal_moves: tuple[AIMoveDecision, ...]


@dataclass
class ProviderResult:
    provider: str
    decision: AIMoveDecision
    raw_response: dict[str, JSONValue] = field(default_factory=dict)


class ProviderError(Exception):
    def __init__(self, provider: str, message: str):
        self.provider = provider
        self.message = message
        super().__init__(f"[{provider}] {message}")


class ProviderTimeoutError(ProviderError):
    pass


class ProviderUnavailableError(ProviderError):
    pass


class ProviderInvalidResponseError(ProviderError):
    pass


class ProviderIllegalMoveError(ProviderError):
    pass
