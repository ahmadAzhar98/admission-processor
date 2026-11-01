"""FastAPI application exposing the review queue to university staff.

Every route requires ``X-Tenant-Id`` and a staff ``X-Api-Key``; the
tenant from the credential scopes every query, so staff of one
university can never address another university's documents.
"""

import logging
from collections.abc import Callable
from typing import Annotated

from common.auth import default_authenticator
from common.errors import AdmissionError
from common.repositories import AuditEntry
from common.repositories.reviews import ReviewItem
from common.runtime import Runtime, get_runtime
from common.tenant import RequestContext, bind_context
from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response

from .service import (
    Resolution,
    ReviewDetail,
    ReviewSummary,
    list_reviews,
    resolve,
    review_detail,
)

logger = logging.getLogger(__name__)


def create_app(runtime: Callable[[], Runtime] = get_runtime) -> FastAPI:
    """Build the app; ``runtime`` is injectable for tests."""
    app = FastAPI(title="Admission review API", version="1")

    @app.exception_handler(AdmissionError)
    def _domain_error(request: Request, exc: AdmissionError) -> JSONResponse:
        logger.warning("review api error", extra={"error": exc.code})
        return JSONResponse(status_code=exc.http_status, content={"error": exc.code})

    def staff_tenant(
        x_tenant_id: Annotated[str | None, Header()] = None,
        x_api_key: Annotated[str | None, Header()] = None,
    ) -> str:
        config = default_authenticator(runtime().tenants).authenticate(
            x_tenant_id, x_api_key, staff=True
        )
        return config.tenant_id

    staff = Depends(staff_tenant)

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/reviews")
    def reviews(tenant_id: Annotated[str, staff], limit: int = 50) -> list[ReviewSummary]:
        with bind_context(RequestContext(tenant_id=tenant_id)):
            return list_reviews(runtime(), tenant_id, min(limit, 200))

    @app.get("/reviews/{document_id}")
    def detail(tenant_id: Annotated[str, staff], document_id: str) -> ReviewDetail:
        with bind_context(RequestContext(tenant_id=tenant_id, document_id=document_id)):
            return review_detail(runtime(), tenant_id, document_id)

    @app.post("/reviews/{document_id}/resolve")
    def resolve_review(
        tenant_id: Annotated[str, staff], document_id: str, body: Resolution
    ) -> ReviewItem:
        with bind_context(RequestContext(tenant_id=tenant_id, document_id=document_id)):
            return resolve(runtime(), tenant_id, document_id, body)

    @app.get("/documents/{document_id}/image")
    def image(tenant_id: Annotated[str, staff], document_id: str) -> Response:
        rt = runtime()
        record = rt.documents.get(tenant_id, document_id)
        data = rt.tenant_storage(tenant_id).get_key(record.document.object_key)
        return Response(content=data, media_type=record.document.content_type)

    @app.get("/documents/{document_id}/audit")
    def audit(tenant_id: Annotated[str, staff], document_id: str) -> list[AuditEntry]:
        return runtime().audit.list(tenant_id, document_id)

    return app


app = create_app()
