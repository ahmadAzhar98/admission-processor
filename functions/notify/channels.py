"""Pluggable delivery channels for applicant notifications.

The platform does not store applicant phone numbers or e-mail addresses;
the university portal owns them. Channels therefore address a message by
application ID: ``log`` writes it (masked) to the function log for
development, and ``webhook`` posts it to the tenant portal, which delivers
it by e-mail or SMS. The tenant's ``channel`` setting names the medium the
portal should use and selects the channel here.
"""

import logging
from typing import Protocol

import httpx
from common.errors import UpstreamServiceError
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Message(BaseModel):
    """A rendered notification ready for delivery."""

    tenant_id: str
    application_id: str
    event: str
    medium: str
    language: str
    text: str


class NotificationChannel(Protocol):
    """Delivers a rendered message."""

    def send(self, message: Message) -> None:
        """Deliver ``message`` or raise UpstreamServiceError."""


class LogChannel:
    """Writes messages to the structured log; for development and tests."""

    def __init__(self) -> None:
        """Keep sent messages for inspection."""
        self.sent: list[Message] = []

    def send(self, message: Message) -> None:
        """Log the message (the formatter masks identifiers)."""
        self.sent.append(message)
        logger.info("notification", extra={"event": message.event, "language": message.language})


class WebhookChannel:
    """Posts messages to the tenant portal's notification endpoint."""

    def __init__(self, url: str, client: httpx.Client | None = None) -> None:
        """Post to ``url``."""
        self.url = url
        self._client = client or httpx.Client(timeout=10.0)

    def send(self, message: Message) -> None:
        """POST the message as JSON; non-2xx responses raise."""
        try:
            response = self._client.post(self.url, json=message.model_dump())
        except httpx.HTTPError as exc:
            raise UpstreamServiceError("notification webhook unreachable") from exc
        if not response.is_success:
            raise UpstreamServiceError(f"notification webhook returned {response.status_code}")


def channel_for(
    medium: str, portal_url: str, client: httpx.Client | None = None
) -> NotificationChannel:
    """Select the channel for a tenant's configured medium.

    ``log`` stays local; any other medium (email, sms, ...) is delivered by
    the portal through its webhook. A non-log medium without a portal URL
    falls back to logging rather than dropping the message silently.
    """
    if medium == "log" or not portal_url:
        return LogChannel()
    return WebhookChannel(portal_url.rstrip("/") + "/api/notifications", client)
