"""Local LLM access through Ollama, behind a small interface.

All model calls stay inside the deployment: documents and extracted
fields are never sent to a hosted API. Responses are constrained to a
JSON schema with Ollama's structured outputs and validated by callers.
"""

import base64
import json
import logging
import zlib
from collections.abc import Callable
from typing import Any, Protocol

import httpx

from common.errors import UpstreamServiceError

logger = logging.getLogger(__name__)


class LlmClient(Protocol):
    """Structured completion and text embedding."""

    def complete_json(
        self, prompt: str, schema: dict[str, Any], images: list[bytes] | None = None
    ) -> dict[str, Any]:
        """Return the model's answer to ``prompt`` as JSON matching ``schema``."""

    def embed(self, text: str) -> list[float]:
        """Return an embedding vector for ``text``."""


class OllamaClient:
    """:class:`LlmClient` over the Ollama HTTP API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        embedding_model: str,
        timeout: float = 60.0,
        client: httpx.Client | None = None,
    ) -> None:
        """Talk to Ollama at ``base_url`` using the named models."""
        self._base = base_url.rstrip("/")
        self.model = model
        self.embedding_model = embedding_model
        self._client = client or httpx.Client(timeout=timeout)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(f"{self._base}{path}", json=payload)
            response.raise_for_status()
            body: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamServiceError(f"ollama request to {path} failed") from exc
        return body

    def complete_json(
        self, prompt: str, schema: dict[str, Any], images: list[bytes] | None = None
    ) -> dict[str, Any]:
        """Generate deterministically (temperature 0) with a JSON schema.

        Raises:
            UpstreamServiceError: If Ollama fails or returns non-JSON text.
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "format": schema,
            "stream": False,
            "options": {"temperature": 0},
        }
        if images:
            payload["images"] = [base64.b64encode(img).decode("ascii") for img in images]
        body = self._post("/api/generate", payload)
        try:
            answer = json.loads(body.get("response", ""))
        except json.JSONDecodeError as exc:
            raise UpstreamServiceError("ollama returned invalid json") from exc
        if not isinstance(answer, dict):
            raise UpstreamServiceError("ollama returned a non-object")
        return answer

    def embed(self, text: str) -> list[float]:
        """Embed ``text`` with the embedding model."""
        body = self._post("/api/embed", {"model": self.embedding_model, "input": text})
        try:
            return [float(v) for v in body["embeddings"][0]]
        except (KeyError, IndexError, TypeError) as exc:
            raise UpstreamServiceError("ollama returned no embedding") from exc


class FakeLlmClient:
    """Scripted client for tests: answers come from a function of the prompt."""

    def __init__(
        self,
        answer: Callable[[str], dict[str, Any]] | None = None,
        dimensions: int = 768,
    ) -> None:
        """Answer prompts with ``answer``; embeddings are deterministic hashes."""
        self._answer = answer or (lambda prompt: {})
        self.dimensions = dimensions
        self.prompts: list[str] = []

    def complete_json(
        self, prompt: str, schema: dict[str, Any], images: list[bytes] | None = None
    ) -> dict[str, Any]:
        """Record ``prompt`` and return the scripted answer."""
        self.prompts.append(prompt)
        return self._answer(prompt)

    def embed(self, text: str) -> list[float]:
        """Bag-of-character-trigrams vector: similar texts get similar vectors.

        Uses CRC32 rather than ``hash()`` so vectors are stable across runs.
        """
        vector = [0.0] * self.dimensions
        lowered = text.lower()
        for i in range(len(lowered) - 2):
            trigram = lowered[i : i + 3].encode("utf-8")
            vector[zlib.crc32(trigram) % self.dimensions] += 1.0
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norm for v in vector]
