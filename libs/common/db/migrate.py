"""Apply the SQL files in ``migrations/`` in order, exactly once each.

Run with ``python -m common.db.migrate``; the database URL comes from
settings. Applied versions are recorded in ``schema_migrations``.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from common.log import configure_logging
from common.settings import get_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Migration:
    """One SQL migration file."""

    version: str
    sql: str


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """Return migrations sorted by their numeric file-name prefix."""
    return [
        Migration(version=path.stem, sql=path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    ]


def apply_pending(conn: Any, migrations: list[Migration]) -> list[str]:
    """Apply migrations not yet recorded, each in its own transaction.

    Args:
        conn: An open psycopg connection.
        migrations: Candidates, in order.

    Returns:
        The versions applied by this call.
    """
    with conn.transaction():
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
    done = {row["version"] if isinstance(row, dict) else row[0] for row in rows}
    applied: list[str] = []
    for migration in migrations:
        if migration.version in done:
            continue
        with conn.transaction():
            conn.execute(migration.sql)
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (migration.version,)
            )
        logger.info("applied migration", extra={"version": migration.version})
        applied.append(migration.version)
    return applied


def main() -> None:
    """Connect using settings and apply all pending migrations."""
    import psycopg

    settings = get_settings()
    configure_logging(settings.log_level)
    with psycopg.connect(settings.database_url.get_secret_value()) as conn:
        apply_pending(conn, discover())


if __name__ == "__main__":
    main()
