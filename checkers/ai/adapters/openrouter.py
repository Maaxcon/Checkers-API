from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from urllib import error, request

from checkers.ai.models import RawResponse


class CheckersOpenRouterTransportError(Exception):
    pass


class CheckersOpenRouterTimeoutError(CheckersOpenRouterTransportError):
    pass


class CheckersOpenRouterNetworkError(CheckersOpenRouterTransportError):
    pass


class CheckersOpenRouterHTTPStatusError(CheckersOpenRouterTransportError):
    def __init__(self, status_code: int, response_body: str):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"OpenRouter HTTP {status_code}: {response_body}")


class CheckersOpenRouterResponseFormatError(CheckersOpenRouterTransportError):
    pass


@dataclass(frozen=True)
class CheckersOpenRouterHTTPAdapter:
    api_key: str
    timeout_ms: int = 8000
    base_url: str = "https://openrouter.ai/api/v1"

    def create_chat_completion(self, payload: RawResponse) -> RawResponse:
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url=f"{self.base_url}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            with request.urlopen(req, timeout=self.timeout_ms / 1000) as response:
                raw_body = response.read().decode("utf-8")
        except TimeoutError as exc:
            raise CheckersOpenRouterTimeoutError("OpenRouter request timed out") from exc
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise CheckersOpenRouterHTTPStatusError(exc.code, error_body) from exc
        except error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, (TimeoutError, socket.timeout)) or "timed out" in str(reason).lower():
                raise CheckersOpenRouterTimeoutError("OpenRouter request timed out") from exc
            raise CheckersOpenRouterNetworkError(f"OpenRouter network error: {reason}") from exc

        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise CheckersOpenRouterResponseFormatError("OpenRouter response is not valid JSON") from exc

        if not isinstance(parsed, dict):
            raise CheckersOpenRouterResponseFormatError("OpenRouter response must be a JSON object")

        return parsed
