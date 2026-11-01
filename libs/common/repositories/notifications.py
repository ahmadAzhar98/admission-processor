"""Exactly-once bookkeeping for applicant notifications.

A notification is *claimed* before it is sent. A second claim for the
same (tenant, subject, event) fails, so queue redelivery cannot message
an applicant twice. If sending fails the claim is released, so the retry
can send it. A crash between sending and recording could still lose the
record; duplicates are the lesser risk than silence, so the claim
happens first.
"""

from typing import Protocol

from common.db.database import Database


class NotificationLog(Protocol):
    """Claims and releases notification slots."""

    def claim(
        self, tenant_id: str, subject_id: str, event: str, channel: str, language: str
    ) -> bool:
        """Return ``True`` if this caller may send; ``False`` if already sent."""

    def release(self, tenant_id: str, subject_id: str, event: str) -> None:
        """Forget a claim after a failed send."""


class InMemoryNotificationLog:
    """Set-backed notification log for tests."""

    def __init__(self) -> None:
        """Start empty."""
        self.sent: dict[tuple[str, str, str], tuple[str, str]] = {}

    def claim(
        self, tenant_id: str, subject_id: str, event: str, channel: str, language: str
    ) -> bool:
        """Claim the slot if free."""
        key = (tenant_id, subject_id, event)
        if key in self.sent:
            return False
        self.sent[key] = (channel, language)
        return True

    def release(self, tenant_id: str, subject_id: str, event: str) -> None:
        """Drop the claim."""
        self.sent.pop((tenant_id, subject_id, event), None)


class PostgresNotificationLog:
    """Notification log in ``notifications`` using the primary key as the lock."""

    def __init__(self, db: Database) -> None:
        """Use ``db`` for all statements."""
        self._db = db

    def claim(
        self, tenant_id: str, subject_id: str, event: str, channel: str, language: str
    ) -> bool:
        """Insert the row; a conflict means it was already claimed."""
        inserted = self._db.execute(
            "INSERT INTO notifications (tenant_id, subject_id, event, channel, language)"
            " VALUES (%(tenant_id)s, %(subject_id)s, %(event)s, %(channel)s, %(language)s)"
            " ON CONFLICT DO NOTHING",
            {
                "tenant_id": tenant_id,
                "subject_id": subject_id,
                "event": event,
                "channel": channel,
                "language": language,
            },
        )
        return inserted == 1

    def release(self, tenant_id: str, subject_id: str, event: str) -> None:
        """Delete the claim."""
        self._db.execute(
            "DELETE FROM notifications WHERE tenant_id = %(tenant_id)s"
            " AND subject_id = %(subject_id)s AND event = %(event)s",
            {"tenant_id": tenant_id, "subject_id": subject_id, "event": event},
        )
