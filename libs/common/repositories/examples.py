"""Tenant few-shot examples: staff-corrected extractions reused in prompts.

When a reviewer corrects an extraction, the OCR text and corrected
fields become an example for that tenant and document type. Extraction
retrieves the most similar examples by embedding, so each university's
quirks (a board's layout, a district's certificate wording) improve
future extractions for that university only.
"""

import math
from typing import Any, Protocol

from pydantic import BaseModel

from common.db.database import Database
from common.schemas.documents import DocumentType, TenantId


class FewShotExample(BaseModel):
    """One corrected document used as an in-context example."""

    tenant_id: TenantId
    document_type: DocumentType
    source_document_id: str
    ocr_text: str
    fields: dict[str, Any]


class ExampleRepository(Protocol):
    """Stores examples with embeddings and finds the nearest ones."""

    def add(self, example: FewShotExample, embedding: list[float]) -> None:
        """Insert, or replace the example from the same source document."""

    def nearest(
        self, tenant_id: str, document_type: DocumentType, embedding: list[float], k: int
    ) -> list[FewShotExample]:
        """Return up to ``k`` examples of this tenant and type, most similar first."""


def cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two vectors (0 if either is zero)."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class InMemoryExampleRepository:
    """Brute-force cosine search; for tests and evaluation runs."""

    def __init__(self) -> None:
        """Start empty."""
        self.items: dict[tuple[str, str, str], tuple[FewShotExample, list[float]]] = {}

    def add(self, example: FewShotExample, embedding: list[float]) -> None:
        """Insert or replace by (tenant, type, source document)."""
        key = (example.tenant_id, example.document_type.value, example.source_document_id)
        self.items[key] = (example, embedding)

    def nearest(
        self, tenant_id: str, document_type: DocumentType, embedding: list[float], k: int
    ) -> list[FewShotExample]:
        """Return the ``k`` most similar examples of this tenant and type."""
        candidates = [
            (cosine(embedding, vector), example)
            for example, vector in self.items.values()
            if example.tenant_id == tenant_id and example.document_type == document_type
        ]
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return [example for _, example in candidates[:k]]


def vector_literal(embedding: list[float]) -> str:
    """Render a vector in pgvector's text format, e.g. ``[0.1,0.2]``."""
    return "[" + ",".join(f"{v:.6f}" for v in embedding) + "]"


class PostgresExampleRepository:
    """Examples in ``tenant_examples``, searched with pgvector cosine distance."""

    def __init__(self, db: Database) -> None:
        """Use ``db`` for all statements."""
        self._db = db

    def add(self, example: FewShotExample, embedding: list[float]) -> None:
        """Upsert by (tenant, type, source document)."""
        from psycopg.types.json import Jsonb

        self._db.execute(
            "INSERT INTO tenant_examples"
            " (tenant_id, document_type, source_document_id, ocr_text, fields, embedding)"
            " VALUES (%(tenant_id)s, %(document_type)s, %(source_document_id)s, %(ocr_text)s,"
            " %(fields)s, %(embedding)s::vector)"
            " ON CONFLICT (tenant_id, document_type, source_document_id) DO UPDATE SET"
            " ocr_text = EXCLUDED.ocr_text, fields = EXCLUDED.fields,"
            " embedding = EXCLUDED.embedding, created_at = now()",
            {
                **example.model_dump(mode="json", exclude={"fields"}),
                "fields": Jsonb(example.fields),
                "embedding": vector_literal(embedding),
            },
        )

    def nearest(
        self, tenant_id: str, document_type: DocumentType, embedding: list[float], k: int
    ) -> list[FewShotExample]:
        """Return the ``k`` nearest examples using the HNSW cosine index."""
        rows = self._db.fetch_all(
            "SELECT tenant_id, document_type, source_document_id, ocr_text, fields"
            " FROM tenant_examples WHERE tenant_id = %(tenant_id)s"
            " AND document_type = %(document_type)s"
            " ORDER BY embedding <=> %(embedding)s::vector LIMIT %(k)s",
            {
                "tenant_id": tenant_id,
                "document_type": document_type.value,
                "embedding": vector_literal(embedding),
                "k": k,
            },
        )
        return [FewShotExample.model_validate(row) for row in rows]
