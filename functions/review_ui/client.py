"""Typed HTTP client for the review API, used by the Streamlit UI."""

from typing import Any

import httpx
from common.errors import UpstreamServiceError


class ReviewClient:
    """Calls the review API with a tenant's staff credentials."""

    def __init__(
        self, base_url: str, tenant_id: str, api_key: str, client: httpx.Client | None = None
    ) -> None:
        """Talk to ``base_url`` as staff of ``tenant_id``."""
        self._client = client or httpx.Client(timeout=15.0)
        self._base = base_url.rstrip("/")
        self._headers = {"X-Tenant-Id": tenant_id, "X-Api-Key": api_key}

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(
                method, f"{self._base}{path}", headers=self._headers, **kwargs
            )
        except httpx.HTTPError as exc:
            raise UpstreamServiceError("review api unreachable") from exc
        if response.status_code >= 400:
            code = response.json().get("error", response.status_code) if response.content else ""
            raise UpstreamServiceError(f"review api error: {code}")
        return response

    def queue(self, limit: int = 50) -> list[dict[str, Any]]:
        """Open review items, oldest first."""
        items: list[dict[str, Any]] = self._request(
            "GET", "/reviews", params={"limit": limit}
        ).json()
        return items

    def detail(self, document_id: str) -> dict[str, Any]:
        """Fields, rule outcomes and decision for one document."""
        detail: dict[str, Any] = self._request("GET", f"/reviews/{document_id}").json()
        return detail

    def image(self, document_id: str) -> bytes:
        """The uploaded image."""
        return self._request("GET", f"/documents/{document_id}/image").content

    def resolve(
        self, document_id: str, outcome: str, reviewer: str, corrections: dict[str, Any]
    ) -> dict[str, Any]:
        """Approve or reject the document with optional corrections."""
        body = {"outcome": outcome, "reviewer": reviewer, "corrections": corrections}
        result: dict[str, Any] = self._request(
            "POST", f"/reviews/{document_id}/resolve", json=body
        ).json()
        return result


def changed_fields(original: list[dict[str, Any]], edited: dict[str, str]) -> dict[str, Any]:
    """Return only the fields whose edited text differs from the extracted value.

    Empty edits mean "leave as is", so a reviewer who only looks at a field
    does not turn it into a correction.
    """
    values = {f["name"]: f["value"] for f in original}
    return {
        name: text.strip()
        for name, text in edited.items()
        if text.strip() and text.strip() != str(values.get(name, "") or "")
    }
