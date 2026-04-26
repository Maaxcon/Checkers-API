from __future__ import annotations

import json

from checkers.ai.adapters import CheckersOpenRouterHTTPAdapter, CheckersOpenRouterHTTPError
from checkers.ai.contracts import CheckersAIMoveProvider
from checkers.ai.models import (
    CheckersAIMoveContext,
    CheckersAIMoveDecision,
    CheckersAIProviderInvalidResponseError,
    CheckersAIProviderResult,
    CheckersAIProviderTimeoutError,
    CheckersAIProviderUnavailableError,
    JSONValue,
    RawResponse,
)
from checkers.services.converters import board_to_json


class CheckersOpenRouterProvider(CheckersAIMoveProvider):
    def __init__(
        self,
        model_name: str,
        adapter: CheckersOpenRouterHTTPAdapter,
        max_retries: int = 2,
    ):
        if not model_name.strip():
            raise ValueError("model_name must not be empty")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")

        self.model_name = model_name.strip()
        self.adapter = adapter
        self.max_retries = max_retries
        self.provider_name = f"checkers-openrouter:{self.model_name}"

    def choose_move(self, context: CheckersAIMoveContext) -> CheckersAIProviderResult:
        payload = self._build_payload(context)
        last_error_message = ""

        for _ in range(self.max_retries + 1):
            try:
                raw_response = self.adapter.create_chat_completion(payload)
                decision = self._extract_decision(raw_response)
                return CheckersAIProviderResult(
                    provider=self.provider_name,
                    decision=decision,
                    raw_response=raw_response,
                )
            except CheckersOpenRouterHTTPError as error:
                last_error_message = str(error)
                if self._is_timeout_error(last_error_message):
                    raise CheckersAIProviderTimeoutError(self.provider_name, last_error_message) from error
            except CheckersAIProviderInvalidResponseError:
                raise

        raise CheckersAIProviderUnavailableError(self.provider_name, last_error_message or "OpenRouter unavailable")

    def _build_payload(self, context: CheckersAIMoveContext) -> RawResponse:
        legal_moves_payload = [
            {
                "from_row": move.from_row,
                "from_col": move.from_col,
                "to_row": move.to_row,
                "to_col": move.to_col,
            }
            for move in context.legal_moves
        ]

        user_content = {
            "game_id": context.game_id,
            "current_turn": context.current_turn,
            "difficulty": context.difficulty,
            "board": board_to_json(context.board),
            "legal_moves": legal_moves_payload,
            "task": "Return only one legal move from legal_moves.",
            "output_schema": {
                "from_row": "int",
                "from_col": "int",
                "to_row": "int",
                "to_col": "int",
            },
        }

        return {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a checkers move selector. "
                        "Return strict JSON with keys: from_row, from_col, to_row, to_col."
                    ),
                },
                {"role": "user", "content": json.dumps(user_content)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }

    def _extract_decision(self, raw_response: RawResponse) -> CheckersAIMoveDecision:
        content = self._extract_message_content(raw_response)
        decision_obj = self._parse_content_to_object(content)
        from_row = self._read_int(decision_obj, "from_row", "fromRow")
        from_col = self._read_int(decision_obj, "from_col", "fromCol")
        to_row = self._read_int(decision_obj, "to_row", "toRow")
        to_col = self._read_int(decision_obj, "to_col", "toCol")
        return CheckersAIMoveDecision(
            from_row=from_row,
            from_col=from_col,
            to_row=to_row,
            to_col=to_col,
        )

    def _extract_message_content(self, raw_response: RawResponse) -> JSONValue:
        choices = raw_response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise CheckersAIProviderInvalidResponseError(self.provider_name, "Missing choices in response")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise CheckersAIProviderInvalidResponseError(self.provider_name, "Invalid choice structure")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise CheckersAIProviderInvalidResponseError(self.provider_name, "Missing message in choice")

        if "content" not in message:
            raise CheckersAIProviderInvalidResponseError(self.provider_name, "Missing content in message")

        return message["content"]

    def _parse_content_to_object(self, content: JSONValue) -> dict[str, JSONValue]:
        if isinstance(content, dict):
            return content

        if isinstance(content, str):
            cleaned = self._strip_code_fence(content)
            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError as error:
                raise CheckersAIProviderInvalidResponseError(
                    self.provider_name,
                    "Message content is not valid JSON",
                ) from error

            if not isinstance(parsed, dict):
                raise CheckersAIProviderInvalidResponseError(self.provider_name, "Parsed content must be JSON object")

            return parsed

        raise CheckersAIProviderInvalidResponseError(self.provider_name, "Unsupported message content format")

    def _read_int(self, data: dict[str, JSONValue], snake_key: str, camel_key: str) -> int:
        value = data.get(snake_key, data.get(camel_key))
        if not isinstance(value, int):
            raise CheckersAIProviderInvalidResponseError(self.provider_name, f"Field {snake_key} must be int")
        return value

    def _strip_code_fence(self, raw: str) -> str:
        text = raw.strip()
        if not text.startswith("```"):
            return text

        lines = text.splitlines()
        if not lines:
            return text

        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _is_timeout_error(self, message: str) -> bool:
        lower = message.lower()
        return "timed out" in lower or "timeout" in lower
