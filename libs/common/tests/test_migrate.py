from contextlib import contextmanager

from common.db.migrate import Migration, apply_pending, discover


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchall(self):
        return self.rows


class FakeConn:
    def __init__(self, applied=()):
        self.applied = list(applied)
        self.statements = []

    @contextmanager
    def transaction(self):
        yield

    def execute(self, sql, params=None):
        self.statements.append(sql)
        if sql.startswith("INSERT INTO schema_migrations"):
            self.applied.append(params[0])
        return FakeResult([(v,) for v in self.applied])


def test_discover_finds_shipped_migrations_in_order():
    versions = [m.version for m in discover()]
    assert versions[0] == "0001_initial"
    assert versions == sorted(versions)


def test_discover_ignores_unnumbered_files(tmp_path):
    (tmp_path / "0002_b.sql").write_text("B")
    (tmp_path / "0001_a.sql").write_text("A")
    (tmp_path / "notes.sql").write_text("X")
    assert [m.version for m in discover(tmp_path)] == ["0001_a", "0002_b"]


def test_only_pending_migrations_are_applied():
    conn = FakeConn(applied=["0001_a"])
    migrations = [Migration("0001_a", "SQL A"), Migration("0002_b", "SQL B")]
    assert apply_pending(conn, migrations) == ["0002_b"]
    assert "SQL A" not in conn.statements
    assert "SQL B" in conn.statements


def test_rerun_is_a_noop():
    conn = FakeConn()
    migrations = [Migration("0001_a", "SQL A")]
    assert apply_pending(conn, migrations) == ["0001_a"]
    assert apply_pending(conn, migrations) == []
