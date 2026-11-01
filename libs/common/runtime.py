"""Dependency container shared by function handlers.

Handlers call :func:`get_runtime` to obtain storage, repositories, the
tenant registry and the event publisher. In a deployed function these are
built once per warm replica from settings; tests install an in-memory
runtime with :func:`set_runtime` so no network or database is touched.
"""

from dataclasses import dataclass
from pathlib import Path

from common.db.database import Database, connect_factory
from common.events import EventPublisher, GatewayPublisher, InMemoryPublisher
from common.repositories import AuditRepository, DocumentRepository, ResultRepository
from common.repositories.memory import (
    InMemoryAuditRepository,
    InMemoryDocumentRepository,
    InMemoryResultRepository,
)
from common.repositories.postgres import (
    PostgresAuditRepository,
    PostgresDocumentRepository,
    PostgresResultRepository,
)
from common.settings import Settings, get_settings
from common.storage import InMemoryObjectStore, ObjectStore, TenantStorage
from common.storage.s3 import S3ObjectStore
from common.tenant_config.loader import TenantRegistry


@dataclass
class Runtime:
    """Everything a pipeline step needs from the outside world."""

    settings: Settings
    tenants: TenantRegistry
    storage: ObjectStore
    documents: DocumentRepository
    results: ResultRepository
    audit: AuditRepository
    publisher: EventPublisher
    database: Database | None = None

    def tenant_storage(self, tenant_id: str) -> TenantStorage:
        """Return storage restricted to ``tenant_id``'s key prefix."""
        return TenantStorage(self.storage, tenant_id)


def build_runtime(settings: Settings) -> Runtime:
    """Wire production dependencies: S3, PostgreSQL and the OpenFaaS gateway."""
    database = Database(connect_factory(settings.database_url.get_secret_value()))
    return Runtime(
        settings=settings,
        tenants=TenantRegistry(settings.tenants_dir),
        storage=S3ObjectStore.from_settings(settings),
        documents=PostgresDocumentRepository(database),
        results=PostgresResultRepository(database),
        audit=PostgresAuditRepository(database),
        publisher=GatewayPublisher(settings.gateway_url),
        database=database,
    )


def in_memory_runtime(tenants_dir: Path, settings: Settings | None = None) -> Runtime:
    """Wire in-memory dependencies for tests and local experiments."""
    audit = InMemoryAuditRepository()
    return Runtime(
        settings=settings or Settings(environment="test", tenants_dir=tenants_dir),
        tenants=TenantRegistry(tenants_dir),
        storage=InMemoryObjectStore(),
        documents=InMemoryDocumentRepository(audit),
        results=InMemoryResultRepository(),
        audit=audit,
        publisher=InMemoryPublisher(),
    )


_runtime: Runtime | None = None


def get_runtime() -> Runtime:
    """Return the process-wide runtime, building it on first use."""
    global _runtime
    if _runtime is None:
        _runtime = build_runtime(get_settings())
    return _runtime


def set_runtime(runtime: Runtime | None) -> None:
    """Install ``runtime`` (or reset with ``None``); intended for tests."""
    global _runtime
    _runtime = runtime
