from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable


@dataclass
class Migration:
    version: str
    description: str
    up: Callable  # sync callable(connection) -> None, connection is a SQLAlchemy sync Connection


MIGRATIONS: list[Migration] = []


def run_migrations(connection) -> None:
    """Run all unapplied migrations in version order.

    Accepts a synchronous SQLAlchemy Connection (for use with conn.run_sync()).
    Checks schema_versions for applied migrations, runs only unapplied ones,
    and records each newly applied migration.
    """
    from sqlalchemy import text as sa_text

    # Ensure schema_versions table exists (may not exist on very first run)
    try:
        connection.execute(sa_text(
            "CREATE TABLE IF NOT EXISTS schema_versions ("
            "  id SERIAL PRIMARY KEY,"
            "  version VARCHAR NOT NULL UNIQUE,"
            "  description VARCHAR NOT NULL,"
            "  applied_at TIMESTAMPTZ NOT NULL"
            ")"
        ))
    except Exception:
        pass  # Table may already exist from prior DDL

    # Query already-applied versions
    result = connection.execute(sa_text("SELECT version FROM schema_versions"))
    applied = {row[0] for row in result}

    # Sort MIGRATIONS by version
    sorted_migrations = sorted(MIGRATIONS, key=lambda m: [int(x) for x in m.version.split(".")])

    now = datetime.now(timezone.utc)
    for migration in sorted_migrations:
        if migration.version in applied:
            print(f"[Migration] {migration.version} already applied — skip")
            continue

        print(f"[Migration] Applying {migration.version}: {migration.description}")
        try:
            migration.up(connection)
        except Exception as e:
            print(f"[Migration] {migration.version} FAILED: {e}")
            raise

        connection.execute(
            sa_text(
                "INSERT INTO schema_versions (version, description, applied_at) "
                "VALUES (:version, :description, :ts)"
                " ON CONFLICT (version) DO NOTHING"
            ),
            {"version": migration.version, "description": migration.description, "ts": now},
        )
        print(f"[Migration] {migration.version} applied successfully")
