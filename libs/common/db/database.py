"""Tenant-guarded query helper over a psycopg connection.

:class:`Database` refuses to run a statement unless it references the
``%(tenant_id)s`` parameter and the parameter is supplied. A forgotten
tenant filter therefore fails loudly in tests instead of leaking data
between universities in production.
"""

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row

from common.errors import DatabaseError
from common.tenant import validate_tenant_id

Row = dict[str, Any]
ConnectionFactory = Callable[[], "psycopg.Connection[Row]"]

TENANT_PARAM = "%(tenant_id)s"


def connect_factory(dsn: str) -> ConnectionFactory:
    """Return a factory opening dict-row connections to ``dsn``."""

    def factory() -> "psycopg.Connection[Row]":
        return psycopg.connect(dsn, row_factory=dict_row)

    return factory


def check_tenant_scoped(sql: str, params: Mapping[str, Any]) -> None:
    """Raise unless ``sql`` filters on a valid ``tenant_id`` parameter.

    Raises:
        DatabaseError: If the placeholder or parameter is missing.
        TenantError: If the tenant ID is not a valid slug.
    """
    if TENANT_PARAM not in sql:
        raise DatabaseError("query is not scoped by %(tenant_id)s")
    if "tenant_id" not in params:
        raise DatabaseError("tenant_id parameter missing")
    validate_tenant_id(str(params["tenant_id"]))


class Database:
    """Lazily connected, reconnecting wrapper used by repositories.

    A warm OpenFaaS replica reuses one connection across invocations; a
    closed or broken connection is replaced on next use.
    """

    def __init__(self, factory: ConnectionFactory) -> None:
        """Use ``factory`` to open connections on demand."""
        self._factory = factory
        self._conn: psycopg.Connection[Row] | None = None

    def _connection(self) -> "psycopg.Connection[Row]":
        if self._conn is None or self._conn.closed:
            try:
                self._conn = self._factory()
            except psycopg.Error as exc:
                raise DatabaseError("could not connect to database") from exc
        return self._conn

    @contextmanager
    def transaction(self) -> Iterator["psycopg.Connection[Row]"]:
        """Run the enclosed statements atomically, committing on success."""
        conn = self._connection()
        try:
            with conn.transaction():
                yield conn
        except psycopg.Error as exc:
            raise DatabaseError("transaction failed") from exc

    def execute(self, sql: str, params: Mapping[str, Any]) -> int:
        """Run a tenant-scoped statement and return the affected row count."""
        check_tenant_scoped(sql, params)
        with self.transaction() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def fetch_one(self, sql: str, params: Mapping[str, Any]) -> Row | None:
        """Run a tenant-scoped query and return the first row or ``None``."""
        check_tenant_scoped(sql, params)
        with self.transaction() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()

    def fetch_all(self, sql: str, params: Mapping[str, Any]) -> list[Row]:
        """Run a tenant-scoped query and return all rows."""
        check_tenant_scoped(sql, params)
        with self.transaction() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()

    def close(self) -> None:
        """Close the cached connection, if any."""
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
        self._conn = None
