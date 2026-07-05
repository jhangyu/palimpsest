"""
---
name: database_router
description: "Database management API routes: schema status, migrations, export (ZIP/JSON), and import"
type: router
target:
  layer: backend
  domain: database
spec_doc: null
test_file: tests/stage1/test_database_router.py
functions:
  - name: database_status
    line: 233
    purpose: "GET /settings/database/status — return schema version, table row counts, pending migrations"
  - name: database_migrate
    line: 239
    purpose: "POST /settings/database/migrate — execute all pending schema migrations in a transaction"
  - name: database_export
    line: 274
    purpose: "GET /settings/database/export — export tables as ZIP (default) or JSON file download"
  - name: database_import_preview
    line: 323
    purpose: "POST /settings/database/import/preview — validate import file and return conflict counts"
  - name: database_import
    line: 353
    purpose: "POST /settings/database/import — import data from JSON/ZIP with skip or overwrite mode"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

import io
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File
from fastapi.responses import StreamingResponse

from core.db import get_db, schema_versions

from routers._deps import require_admin, _csrf_dependency
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
    await db.commit()

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
