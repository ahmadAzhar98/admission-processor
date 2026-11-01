import json

import httpx
import pytest

from common.errors import UpstreamServiceError
from common.llm import FakeLlmClient, OllamaClient


def _client(handler) -> OllamaClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OllamaClient("http://ollama:11434/", "qwen", "nomic", client=http)


def test_complete_json_sends_schema_and_parses_answer():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"response": json.dumps({"document_type": "cnic"})})

    answer = _client(handler).complete_json("classify", {"type": "object"}, images=[b"img"])
    assert answer == {"document_type": "cnic"}
    assert seen["format"] == {"type": "object"}
    assert seen["options"] == {"temperature": 0}
    assert seen["images"] == ["aW1n"]
    assert seen["stream"] is False


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500),
        httpx.Response(200, json={"response": "not json"}),
        httpx.Response(200, json={"response": "[1, 2]"}),
    ],
)
def test_bad_responses_raise(response):
    with pytest.raises(UpstreamServiceError):
        _client(lambda request: response).complete_json("x", {})


def test_embed():
    client = _client(lambda request: httpx.Response(200, json={"embeddings": [[0.1, 0.2]]}))
    assert client.embed("text") == [0.1, 0.2]


def test_fake_embeddings_reflect_similarity():
    fake = FakeLlmClient(dimensions=256)

    def cosine(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    base = fake.embed("Higher Secondary School Certificate BISE Lahore")
    similar = fake.embed("Higher Secondary School Certificate BISE Multan")
    different = fake.embed("Fee Challan Bank A amount paid")
    assert cosine(base, similar) > cosine(base, different)
