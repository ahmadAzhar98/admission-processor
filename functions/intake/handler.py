"""OpenFaaS entry point for intake.

``POST`` the raw file bytes with headers ``X-Tenant-Id``, ``X-Api-Key``,
``X-Application-Id``, ``Content-Type`` and optionally ``X-Document-Type``.
Responds 202 for a new document and 200 for a duplicate upload.
"""

from typing import Any

from common.auth import default_authenticator
from common.http import (
    HttpEvent,
    Response,
    body_bytes,
    header,
    http_handler,
    json_response,
    parse_model,
)
from common.runtime import get_runtime
from common.tenant import RequestContext, bind_context

from .service import UploadRequest, accept_upload


@http_handler
def handle(event: HttpEvent, context: Any) -> Response:
    """Authenticate, store and enqueue one uploaded document."""
    if event.method.upper() != "POST":
        return json_response(405, {"error": "method_not_allowed"})
    rt = get_runtime()
    config = default_authenticator(rt.tenants).authenticate(
        header(event, "X-Tenant-Id"), header(event, "X-Api-Key")
    )
    request = parse_model(
        UploadRequest,
        {
            "tenant_id": config.tenant_id,
            "application_id": header(event, "X-Application-Id") or "",
            "content_type": header(event, "Content-Type") or "",
            "declared_type": header(event, "X-Document-Type") or None,
        },
    )
    with bind_context(RequestContext(tenant_id=config.tenant_id)):
        result = accept_upload(rt, request, body_bytes(event))
    return json_response(200 if result.duplicate else 202, result)
