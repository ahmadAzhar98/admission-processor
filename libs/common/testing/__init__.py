"""Test helpers shared by function test suites (never used in production)."""

from dataclasses import dataclass, field


@dataclass
class FakeHttpEvent:
    """Stand-in for the OpenFaaS python3-http request object."""

    body: bytes | str = b""
    headers: dict[str, str] = field(default_factory=dict)
    method: str = "POST"
    query: dict[str, str] = field(default_factory=dict)
    path: str = "/"
