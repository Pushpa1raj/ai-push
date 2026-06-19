from collections.abc import Iterator
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaService:
    base_url = "http://localhost:11434"

    def __init__(self, base_url: str | None = None, timeout: float = 60.0) -> None:
        self.base_url = (base_url or self.base_url).rstrip("/")
        self.timeout = timeout

    def generate(
        self,
        model: str,
        messages: list,
        *,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if options:
            payload["options"] = options

        return self._post_json("/api/chat", payload)

    def stream(
        self,
        model: str,
        messages: list,
        *,
        options: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if options:
            payload["options"] = options

        request = self._request("/api/chat", payload)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                for line in response:
                    if line:
                        yield json.loads(line.decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8")
            raise RuntimeError(f"Ollama request failed: {error.code} {detail}") from error
        except URLError as error:
            raise RuntimeError(f"Unable to connect to Ollama at {self.base_url}") from error

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = self._request(path, payload)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8")
            raise RuntimeError(f"Ollama request failed: {error.code} {detail}") from error
        except URLError as error:
            raise RuntimeError(f"Unable to connect to Ollama at {self.base_url}") from error

    def _request(self, path: str, payload: dict[str, Any]) -> Request:
        return Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
