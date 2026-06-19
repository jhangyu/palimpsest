"""Database management endpoints.

Extracted from backend/main.py — all endpoint logic is a verbatim copy.
"""

import io
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from fastapi.responses import StreamingResponse

from core.db import get_db, schema_versions

from routers._deps import require_admin, _csrf_dependency, log_with_time
from services.export_service import (
    _MAX_IMPORT_FILE_SIZE,
    prepare_export,
    stream_export_json,
    parse_import_file,
    preview_import,
    execute_import,
    compute_database_status,
)

router = APIRouter(prefix="/settings/database", tags=["database"])

# --- App Version & Migration Registry ---
APP_VERSION = "0.1.0"

MIGRATIONS = [
    # {"version": "0.2.0", "description": "Add xyz column", "up": async_migration_fn},
]

# --- Schema Migration ---

def _run_schema_migration(engine):
    """Idempotent schema upgrade for existing databases."""
    from sqlalchemy import text as sa_text

    with engine.connect() as conn:
        # Add new columns to articles if they don't exist
        for col, col_type in [("created_at", "VARCHAR"), ("updated_at", "VARCHAR"), ("word_count", "INTEGER")]:
            try:
                conn.execute(sa_text(f"ALTER TABLE articles ADD COLUMN IF NOT EXISTS {col} {col_type}"))
            except Exception as e:
                log_with_time(f"[Migration] Column articles.{col} migration note: {e}")

        # DD-10: Migrate articles timestamp columns from VARCHAR to TIMESTAMPTZ
        for col in ("published_at", "created_at", "updated_at"):
            try:
                conn.execute(sa_text(
                    f"ALTER TABLE articles ALTER COLUMN {col} TYPE TIMESTAMPTZ "
                    f"USING {col}::timestamptz"
                ))
            except Exception as e:
                # Column may already be TIMESTAMPTZ — safe to ignore
                err_str = str(e).lower()
                if "already" not in err_str and "same type" not in err_str:
                    log_with_time(f"[Migration] articles.{col} TIMESTAMPTZ migration note: {e}")

        # --- Auth tables (CREATE TABLE IF NOT EXISTS) ---
        auth_table_stmts = [
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR NOT NULL UNIQUE,
                email_normalized VARCHAR NOT NULL UNIQUE,
                pending_email VARCHAR,
                pending_email_normalized VARCHAR,
                username VARCHAR NOT NULL UNIQUE,
                username_normalized VARCHAR NOT NULL UNIQUE,
                full_name VARCHAR,
                password_hash TEXT NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'active',
                email_verified_at TIMESTAMPTZ,
                avatar_mime_type VARCHAR,
                avatar_bytes BYTEA,
                avatar_size_bytes INTEGER,
                avatar_hash VARCHAR,
                avatar_source VARCHAR NOT NULL DEFAULT 'none',
                avatar_updated_at TIMESTAMPTZ,
                preferences JSON NOT NULL DEFAULT '{}',
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                last_login_at TIMESTAMPTZ
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS roles (
                id SERIAL PRIMARY KEY,
                name VARCHAR NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMPTZ NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, role_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS auth_sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                token_hash VARCHAR NOT NULL UNIQUE,
                user_agent TEXT,
                ip_address VARCHAR,
                created_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                revoked_at TIMESTAMPTZ
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                token_hash VARCHAR NOT NULL UNIQUE,
                created_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                used_at TIMESTAMPTZ
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS email_verification_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                token_hash VARCHAR NOT NULL UNIQUE,
                email VARCHAR NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                used_at TIMESTAMPTZ
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS auth_rate_limits (
                id SERIAL PRIMARY KEY,
                scope VARCHAR NOT NULL,
                subject_hash VARCHAR NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                window_started_at TIMESTAMPTZ NOT NULL,
                locked_until TIMESTAMPTZ,
                updated_at TIMESTAMPTZ NOT NULL,
                UNIQUE(scope, subject_hash)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS schema_versions (
                id SERIAL PRIMARY KEY,
                version VARCHAR NOT NULL UNIQUE,
                description VARCHAR NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL
            )
            """,
        ]

        for stmt in auth_table_stmts:
            try:
                conn.execute(sa_text(stmt))
            except Exception as e:
                log_with_time(f"[Migration] Auth table creation note: {e}")

        # Create indexes if not exist
        index_stmts = [
            # Existing indexes
            "CREATE INDEX IF NOT EXISTS idx_articles_site_id ON articles(site_id)",
            "CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at)",
            "CREATE INDEX IF NOT EXISTS idx_rss_query_events_requested_at ON rss_query_events(requested_at)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_attempts_started_at ON crawl_attempts(started_at)",
            "CREATE INDEX IF NOT EXISTS idx_crawl_attempts_site_started ON crawl_attempts(site_id, started_at)",
            # Auth indexes
            "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_expires ON auth_sessions(user_id, expires_at, revoked_at)",
            "CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user ON password_reset_tokens(user_id, expires_at, used_at)",
            "CREATE INDEX IF NOT EXISTS idx_email_verification_tokens_user ON email_verification_tokens(user_id, expires_at, used_at)",
            "CREATE INDEX IF NOT EXISTS idx_auth_rate_limits_scope_locked ON auth_rate_limits(scope, locked_until)",
        ]

        for stmt in index_stmts:
            try:
                conn.execute(sa_text(stmt))
            except Exception as e:
                log_with_time(f"[Migration] Index creation note: {e}")

        # Partial unique indexes (PostgreSQL-specific)
        partial_idx_stmts = [
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_pending_email_normalized ON users(pending_email_normalized) WHERE pending_email_normalized IS NOT NULL",
        ]
        for stmt in partial_idx_stmts:
            try:
                conn.execute(sa_text(stmt))
            except Exception as e:
                log_with_time(f"[Migration] Partial unique index note: {e}")

        # Seed roles if not exist
        try:
            now_str = datetime.now(timezone.utc).isoformat()
            conn.execute(sa_text(
                "INSERT INTO roles (name, description, created_at) VALUES (:name, :desc, :ts) ON CONFLICT (name) DO NOTHING"
            ), {"name": "admin", "desc": "Administrator role with full access", "ts": now_str})
            conn.execute(sa_text(
                "INSERT INTO roles (name, description, created_at) VALUES (:name, :desc, :ts) ON CONFLICT (name) DO NOTHING"
            ), {"name": "user", "desc": "Standard user role", "ts": now_str})
        except Exception as e:
            log_with_time(f"[Migration] Role seeding note: {e}")

        conn.commit()
    log_with_time("[Migration] Schema migration completed.")


# --- Endpoints ---

@router.get("/status")
async def database_status(current_user: dict = Depends(require_admin), db=Depends(get_db)):
    """Return database status: schema version, table row counts, pending migrations."""
    return await compute_database_status(db, MIGRATIONS, APP_VERSION)


@router.post("/migrate", dependencies=[Depends(_csrf_dependency)])
async def database_migrate(current_user: dict = Depends(require_admin), db=Depends(get_db)):
    """Execute all pending schema migrations in a transaction."""
    applied_rows = (await db.execute(schema_versions.select())).mappings().all()
    applied_versions = {r["version"] for r in applied_rows}

    pending = [m for m in MIGRATIONS if m["version"] not in applied_versions]
    if not pending:
        return {"applied": [], "message": "No pending migrations"}

    applied = []
    async with db.begin():
        for migration in pending:
            try:
                await migration["up"](db)
                await db.execute(
                    schema_versions.insert().values(
                        version=migration["version"],
                        description=migration["description"],
                        applied_at=datetime.now(timezone.utc),
                    )
                )
                applied.append({
                    "version": migration["version"],
                    "description": migration["description"],
                })
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Migration {migration['version']} failed: {str(e)}",
                )

    return {"applied": applied, "message": f"Applied {len(applied)} migration(s)"}


@router.get("/export")
async def database_export(
    tables: str = "sites,articles",
    include_audit: bool = False,
    format: str = "zip",
    current_user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    """Export database tables as a ZIP (default) or JSON file download.

    Use format=json for plain JSON, format=zip (default) for a ZIP archive.
    """
    try:
        requested_tables, current_version, table_counts = await prepare_export(
            db, tables, include_audit, APP_VERSION
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    export_time = datetime.now(timezone.utc).isoformat()

    if format == "json":
        filename = f"palimpsest-export-{date_str}.json"
        return StreamingResponse(
            stream_export_json(db, requested_tables, export_time, current_version, table_counts, APP_VERSION),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:
        # ZIP: collect streaming JSON then compress (paginated fetch reduces peak memory)
        json_parts = []
        async for chunk in stream_export_json(db, requested_tables, export_time, current_version, table_counts, APP_VERSION):
            json_parts.append(chunk)
        json_str = "".join(json_parts)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('palimpsest-export.json', json_str)
        zip_buffer.seek(0)
        return Response(
            content=zip_buffer.read(),
            media_type='application/zip',
            headers={
                'Content-Disposition': f'attachment; filename="palimpsest-export-{date_str}.zip"'
            }
        )


@router.post("/import/preview", dependencies=[Depends(_csrf_dependency)])
async def database_import_preview(
    current_user: dict = Depends(require_admin),
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    """Preview an import: validate format, check conflicts, return counts.

    Accepts both .json and .zip files.
    """
    file_content = await file.read()
    if len(file_content) > _MAX_IMPORT_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {_MAX_IMPORT_FILE_SIZE // (1024 * 1024)}MB)",
        )

    try:
        import_data = await parse_import_file(file_content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid file: {str(e)}")

    try:
        return await preview_import(db, import_data, APP_VERSION)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import", dependencies=[Depends(_csrf_dependency)])
async def database_import(
    mode: str = "skip",
    current_user: dict = Depends(require_admin),
    file: UploadFile = File(...),
    db=Depends(get_db),
):
    """Import data from a JSON or ZIP export file. mode='skip' or 'overwrite'."""
    if mode not in ("skip", "overwrite"):
        raise HTTPException(status_code=400, detail="mode must be 'skip' or 'overwrite'")

    file_content = await file.read()
    if len(file_content) > _MAX_IMPORT_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {_MAX_IMPORT_FILE_SIZE // (1024 * 1024)}MB)",
        )

    try:
        import_data = await parse_import_file(file_content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid file: {str(e)}")

    try:
        results = await execute_import(db, import_data, mode)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"tables": results}
