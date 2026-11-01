"""Notify step: render the tenant's template and deliver it once."""

import logging
from typing import Any

from common.errors import InvalidRequestError, UpstreamServiceError
from common.repositories import AuditEntry
from common.runtime import Runtime
from common.schemas.events import PipelineEvent
from common.tenant_config.models import TenantConfig
from common.tenant_config.notifications import NotificationEvent

from .channels import Message, NotificationChannel, channel_for

logger = logging.getLogger(__name__)

DOCUMENT_LEVEL = {NotificationEvent.RECEIVED, NotificationEvent.REUPLOAD_REQUIRED}
"""Events about one document; the rest concern the whole application."""


def render(
    config: TenantConfig, event: PipelineEvent, notification: NotificationEvent, document_type: str
) -> Message:
    """Fill the tenant's template for ``notification`` in its default language."""
    settings = config.notifications
    reasons = ", ".join(str(r) for r in event.payload.get("reasons", []))
    text = settings.templates[notification].render(
        settings.default_language,
        {
            "university": config.display_name,
            "application_id": event.application_id,
            "document_type": document_type,
            "reasons": reasons,
            "portal_url": settings.portal_url,
        },
    )
    return Message(
        tenant_id=config.tenant_id,
        application_id=event.application_id,
        event=notification.value,
        medium=settings.channel,
        language=settings.default_language.value,
        text=text,
    )


def process(
    event: PipelineEvent, rt: Runtime, channel: NotificationChannel | None = None
) -> dict[str, Any]:
    """Send the notification named in the payload, at most once per subject.

    Raises:
        InvalidRequestError: If the payload names an unknown notification.
        UpstreamServiceError: If delivery fails (the claim is released so
            the queue's retry can deliver it).
    """
    try:
        notification = NotificationEvent(str(event.payload.get("notification")))
    except ValueError as exc:
        raise InvalidRequestError("unknown notification") from exc
    config = rt.tenants.get(event.tenant_id)
    record = rt.documents.get(event.tenant_id, event.document_id)
    doc_type = record.document_type.value.replace("_", " ") if record.document_type else "document"
    message = render(config, event, notification, doc_type)
    subject = event.document_id if notification in DOCUMENT_LEVEL else event.application_id
    if not rt.notifications.claim(
        event.tenant_id, subject, notification.value, message.medium, message.language
    ):
        return {"sent": False, "reason": "already_sent"}
    sender = channel or channel_for(message.medium, config.notifications.portal_url)
    try:
        sender.send(message)
    except UpstreamServiceError:
        rt.notifications.release(event.tenant_id, subject, notification.value)
        raise
    rt.audit.record(
        AuditEntry(
            tenant_id=event.tenant_id,
            document_id=event.document_id,
            actor="notify",
            action="notification_sent",
            details={"event": notification.value, "medium": message.medium},
        )
    )
    return {"sent": True, "event": notification.value, "language": message.language}
