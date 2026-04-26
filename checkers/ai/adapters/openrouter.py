from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error, request

from checkers.ai.models import RawResponse


class CheckersOpenRouterHTTPError(Exception):
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
        except error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise CheckersOpenRouterHTTPError(f"OpenRouter HTTP {exc.code}: {error_body}") from exc
        except error.URLError as exc:
            raise CheckersOpenRouterHTTPError(f"OpenRouter network error: {exc.reason}") from exc

        try:
            parsed = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise CheckersOpenRouterHTTPError("OpenRouter response is not valid JSON") from exc

        if not isinstance(parsed, dict):
            raise CheckersOpenRouterHTTPError("OpenRouter response must be a JSON object")

        return parsed
