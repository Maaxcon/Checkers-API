from __future__ import annotations

import json

from checkers.ai.adapters import (
    CheckersOpenRouterHTTPAdapter,
    CheckersOpenRouterHTTPStatusError,
    CheckersOpenRouterNetworkError,
    CheckersOpenRouterResponseFormatError,
    CheckersOpenRouterTimeoutError,
)
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
from checkers.ai.validation import validate_checkers_ai_decision_is_legal
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
        attempts = self.max_retries + 1

        for attempt_idx in range(attempts):
            is_last_attempt = attempt_idx == attempts - 1
            try:
                raw_response = self.adapter.create_chat_completion(payload)
                decision = self._extract_decision(raw_response)
                validate_checkers_ai_decision_is_legal(self.provider_name, context, decision)
                return CheckersAIProviderResult(
                    provider=self.provider_name,
                    decision=decision,
                    raw_response=raw_response,
                )
            except CheckersOpenRouterTimeoutError as error:
                if is_last_attempt:
                    raise CheckersAIProviderTimeoutError(self.provider_name, str(error)) from error
            except CheckersOpenRouterNetworkError as error:
                if is_last_attempt:
                    raise CheckersAIProviderUnavailableError(self.provider_name, str(error)) from error
            except CheckersOpenRouterHTTPStatusError as error:
                if self._is_retryable_http_status(error.status_code) and not is_last_attempt:
                    continue
                raise CheckersAIProviderUnavailableError(self.provider_name, str(error)) from error
            except CheckersOpenRouterResponseFormatError as error:
                raise CheckersAIProviderInvalidResponseError(self.provider_name, str(error)) from error
            except CheckersAIProviderInvalidResponseError:
                raise

        raise CheckersAIProviderUnavailableError(self.provider_name, "OpenRouter unavailable")

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

        if "content" in message and message["content"] is not None:
            return message["content"]

        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            return tool_calls

        function_call = message.get("function_call")
        if isinstance(function_call, dict):
            return function_call

        if "content" in message:
            return message["content"]

        raise CheckersAIProviderInvalidResponseError(self.provider_name, "Missing content in message")

    def _parse_content_to_object(self, content: JSONValue) -> dict[str, JSONValue]:
        if isinstance(content, dict):
            if self._contains_decision_fields(content):
                return content

            nested_content = content.get("content")
            if isinstance(nested_content, (dict, list, str)):
                return self._parse_content_to_object(nested_content)

            text_value = self._extract_text_from_content_part(content)
            if text_value is not None:
                return self._parse_json_object_from_text(text_value)

            raise CheckersAIProviderInvalidResponseError(self.provider_name, "Unsupported message content format")

        if isinstance(content, str):
            return self._parse_json_object_from_text(content)

        if isinstance(content, list):
            text_chunks = [
                text
                for text in (self._extract_text_from_content_part(part) for part in content)
                if text is not None and text.strip()
            ]
            if not text_chunks:
                raise CheckersAIProviderInvalidResponseError(self.provider_name, "Unsupported message content format")
            return self._parse_json_object_from_text("\n".join(text_chunks))

        raise CheckersAIProviderInvalidResponseError(self.provider_name, "Unsupported message content format")

    def _read_int(self, data: dict[str, JSONValue], snake_key: str, camel_key: str) -> int:
        value = data.get(snake_key, data.get(camel_key))
        if not isinstance(value, int) or isinstance(value, bool):
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

    def _is_retryable_http_status(self, status_code: int) -> bool:
        return status_code == 408 or status_code == 429 or status_code >= 500

    def _parse_json_object_from_text(self, raw_text: str) -> dict[str, JSONValue]:
        cleaned = self._strip_code_fence(raw_text)
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

    def _contains_decision_fields(self, data: dict[str, JSONValue]) -> bool:
        expected_keys = ("from_row", "from_col", "to_row", "to_col")
        camel_keys = ("fromRow", "fromCol", "toRow", "toCol")
        return all(key in data for key in expected_keys) or all(key in data for key in camel_keys)

    def _extract_text_from_content_part(self, part: JSONValue) -> str | None:
        if isinstance(part, str):
            return part

        if isinstance(part, dict):
            text_value = part.get("text")
            if isinstance(text_value, str):
                return text_value
            if isinstance(text_value, dict):
                text_inner_value = text_value.get("value")
                if isinstance(text_inner_value, str):
                    return text_inner_value

            content_value = part.get("content")
            if isinstance(content_value, str):
                return content_value
            if isinstance(content_value, list):
                nested_text = [
                    text
                    for text in (self._extract_text_from_content_part(item) for item in content_value)
                    if text is not None and text.strip()
                ]
                if nested_text:
                    return "\n".join(nested_text)

            json_value = part.get("json")
            if isinstance(json_value, dict):
                return json.dumps(json_value)

            arguments_value = part.get("arguments")
            if isinstance(arguments_value, str):
                return arguments_value
            if isinstance(arguments_value, dict):
                return json.dumps(arguments_value)

            function_value = part.get("function")
            if isinstance(function_value, dict):
                function_arguments = function_value.get("arguments")
                if isinstance(function_arguments, str):
                    return function_arguments
                if isinstance(function_arguments, dict):
                    return json.dumps(function_arguments)

            return None

        if isinstance(part, list):
            nested_text = [
                text
                for text in (self._extract_text_from_content_part(item) for item in part)
                if text is not None and text.strip()
            ]
            if nested_text:
                return "\n".join(nested_text)

        return None
