from contextlib import contextmanager

import pytest

from common.db.database import Database, check_tenant_scoped
from common.errors import DatabaseError, TenantError


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params):
        self.conn.executed.append((sql, params))

    def fetchone(self):
        return {"n": 1}

    def fetchall(self):
        return [{"n": 1}, {"n": 2}]


class FakeConnection:
    def __init__(self):
        self.executed = []
        self.closed = False

    @contextmanager
    def transaction(self):
        yield

    def cursor(self):
        return FakeCursor(self)

    def close(self):
        self.closed = True


SQL = "SELECT 1 FROM documents WHERE tenant_id = %(tenant_id)s"


def test_unscoped_query_is_refused():
    with pytest.raises(DatabaseError):
        check_tenant_scoped("SELECT * FROM documents", {"tenant_id": "uni-a"})


def test_missing_tenant_param_is_refused():
    with pytest.raises(DatabaseError):
        check_tenant_scoped(SQL, {})


def test_invalid_tenant_param_is_refused():
    with pytest.raises(TenantError):
        check_tenant_scoped(SQL, {"tenant_id": "x' OR 1=1 --"})


def test_queries_run_on_a_reused_connection():
    opened = []

    def factory():
        opened.append(FakeConnection())
        return opened[-1]

    db = Database(factory)
    assert db.fetch_one(SQL, {"tenant_id": "uni-a"}) == {"n": 1}
    assert len(db.fetch_all(SQL, {"tenant_id": "uni-a"})) == 2
    assert db.execute(SQL, {"tenant_id": "uni-a"}) == 1
    assert len(opened) == 1
    assert len(opened[0].executed) == 3


def test_closed_connection_is_replaced():
    opened = []

    def factory():
        opened.append(FakeConnection())
        return opened[-1]

    db = Database(factory)
    db.fetch_one(SQL, {"tenant_id": "uni-a"})
    db.close()
    db.fetch_one(SQL, {"tenant_id": "uni-a"})
    assert len(opened) == 2
