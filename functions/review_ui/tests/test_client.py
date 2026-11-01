import json
from typing import Any

import httpx
import pytest
from common.errors import UpstreamServiceError

from functions.review_ui.client import ReviewClient, changed_fields


def _client(handler):
    return ReviewClient(
        "http://api/", "uni-a", "staff", httpx.Client(transport=httpx.MockTransport(handler))
    )


def test_requests_carry_staff_credentials():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=[{"document_id": "d1"}])

    assert _client(handler).queue(10) == [{"document_id": "d1"}]
    assert seen[0].headers["X-Api-Key"] == "staff"
    assert str(seen[0].url) == "http://api/reviews?limit=10"


def test_resolve_posts_body():
    def handler(request):
        assert json.loads(request.content) == {
            "outcome": "approve",
            "reviewer": "r1",
            "corrections": {"board": "BISE Lahore"},
        }
        return httpx.Response(200, json={"status": "resolved"})

    assert (
        _client(handler).resolve("d1", "approve", "r1", {"board": "BISE Lahore"})["status"]
        == "resolved"
    )


def test_api_errors_raise():
    with pytest.raises(UpstreamServiceError, match="unauthenticated"):
        _client(lambda r: httpx.Response(401, json={"error": "unauthenticated"})).queue()


def test_only_real_changes_become_corrections():
    original: list[dict[str, Any]] = [
        {"name": "board", "value": "BISE Lahor"},
        {"name": "year", "value": 2025},
    ]
    edited = {"board": "BISE Lahore", "year": "2025"}
    assert changed_fields(original, edited) == {"board": "BISE Lahore"}
    assert changed_fields(original, {"board": "  "}) == {}
