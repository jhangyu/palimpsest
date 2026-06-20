"""Export/Import business logic for database management.

Extracted from routers/database.py — pure service layer with no FastAPI dependencies.
Service functions raise ValueError for business-rule violations; the router converts
these to HTTPException.
"""

import asyncio
import io
import json
import zipfile
from datetime import datetime, date as _date_cls, timezone

from sqlalchemy import text

from core.auth import normalize_email, normalize_username
from core.db import (
    metadata, sites, articles, crawl_attempts, rss_query_events,
    users, roles, user_roles, schema_versions,
    crawl_repair_tables,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Import file size limits
_MAX_IMPORT_FILE_SIZE = 50 * 1024 * 1024          # 50 MB
_MAX_IMPORT_UNCOMPRESSED_SIZE = 500 * 1024 * 1024  # 500 MB

# Tables safe to export (never export auth/security tables)
_EXPORTABLE_TABLES = {"sites", "articles", "crawl_attempts", "rss_query_events", "users", "roles", "user_roles", "site_crawl_repair_states", "crawl_repair_attempts"}
_AUDIT_TABLES = {"crawl_attempts", "rss_query_events"}
# System tables excluded from status row counts
_SYSTEM_TABLES = {"schema_versions", "alembic_version"}
# FK import order: parents before children
_IMPORT_ORDER = ["roles", "users", "user_roles", "sites", "articles", "crawl_attempts", "site_crawl_repair_states", "crawl_repair_attempts", "rss_query_events"]

# Table object lookup for exportable tables
_TABLE_MAP = {
    "sites": sites,
    "articles": articles,
    "crawl_attempts": crawl_attempts,
    "rss_query_events": rss_query_events,
    "users": users,
    "roles": roles,
    "user_roles": user_roles,
    "site_crawl_repair_states": crawl_repair_tables.site_crawl_repair_states,
    "crawl_repair_attempts": crawl_repair_tables.crawl_repair_attempts,
}

# Columns to exclude per-table during export (sensitive or derived fields)
_EXPORT_EXCLUDED_COLUMNS = {
    "users": {
        "avatar_bytes",
        "email_normalized",
        "username_normalized",
        "pending_email",
        "pending_email_normalized",
        "password_hash",
    },
    "crawl_repair_attempts": {"provider_trace_id"},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _ExportEncoder(json.JSONEncoder):
    """Custom JSON encoder for database export: handles datetime, date, and bytes."""

    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, _date_cls):
            return o.isoformat()
        if isinstance(o, (bytes, bytearray)):
            return o.decode("utf-8", errors="replace")
        return super().default(o)


def _serialize_row_for_export(row_dict: dict) -> str:
    """Serialize a database row to a JSON string for export."""
    return json.dumps(row_dict, cls=_ExportEncoder, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Export service functions
# ---------------------------------------------------------------------------

async def prepare_export(db, tables_csv: str, include_audit: bool, app_version: str) -> tuple[list[str], str, dict]:
    """Validate tables, compute counts, return (requested_tables, current_version, table_counts).

    Raises ValueError for invalid table names or empty table list.
    """
    requested_tables = [t.strip() for t in tables_csv.split(",") if t.strip()]

    # Validate table names
    invalid = [t for t in requested_tables if t not in _EXPORTABLE_TABLES]
    if invalid:
        raise ValueError(f"Non-exportable table(s): {', '.join(invalid)}")

    # Filter out audit tables unless include_audit
    if not include_audit:
        requested_tables = [t for t in requested_tables if t not in _AUDIT_TABLES]

    if not requested_tables:
        raise ValueError("No valid tables to export")

    # Current schema version
    latest_version = (await db.execute(
        text("SELECT version FROM schema_versions ORDER BY applied_at DESC LIMIT 1")
    )).mappings().first()
    current_version = latest_version["version"] if latest_version else app_version

    # Pre-compute row counts (small queries, not full-table load)
    table_counts: dict = {}
    for t_name in requested_tables:
        cnt_row = (await db.execute(
            text(f'SELECT COUNT(*) AS cnt FROM "{t_name}"')
        )).mappings().first()
        table_counts[t_name] = cnt_row["cnt"] if cnt_row else 0

    return requested_tables, current_version, table_counts


async def stream_export_json(db, requested_tables: list[str], export_time: str, current_version: str, table_counts: dict, app_version: str):
    """Async generator that streams JSON export in 1000-row batches."""
    meta = json.dumps({
        "export_time": export_time,
        "schema_version": current_version,
        "app_version": app_version,
        "tables": table_counts,
    }, ensure_ascii=False)
    yield '{"metadata":' + meta + ',"data":{'

    for i, t_name in enumerate(requested_tables):
        if i > 0:
            yield ","
        yield f'"{t_name}":['
        excluded_cols = _EXPORT_EXCLUDED_COLUMNS.get(t_name, set())
        tbl = _TABLE_MAP[t_name]
        offset = 0
        first_row = True
        while True:
            batch = (await db.execute(tbl.select().limit(1000).offset(offset))).mappings().all()
            if not batch:
                break
            for r in batch:
                row_dict = dict(r)
                for col in excluded_cols:
                    row_dict.pop(col, None)
                if not first_row:
                    yield ","
                yield _serialize_row_for_export(row_dict)
                first_row = False
            offset += 1000
        yield "]"

    yield "}}"


# ---------------------------------------------------------------------------
# Import service functions
# ---------------------------------------------------------------------------

async def parse_import_file(file_content: bytes, filename: str | None) -> dict:
    """Parse and validate an import file (JSON or ZIP). Returns import_data dict.

    Raises ValueError for invalid ZIP, missing JSON, or invalid format.
    File-size validation is the caller's responsibility.
    """
    if filename and filename.lower().endswith('.zip'):
        zip_buffer = io.BytesIO(file_content)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > _MAX_IMPORT_UNCOMPRESSED_SIZE:
                raise ValueError("ZIP uncompressed size exceeds limit")
            json_files = [n for n in zf.namelist() if n.endswith('.json')]
            if not json_files:
                raise ValueError("ZIP file contains no JSON files")
            json_content = zf.read(json_files[0])
            import_data = json.loads(json_content)
    else:
        import_data = json.loads(file_content)

    if "metadata" not in import_data or "data" not in import_data:
        raise ValueError("Invalid export format: missing 'metadata' or 'data'")

    return import_data


async def preview_import(db, import_data: dict, app_version: str) -> dict:
    """Preview import: check schema compatibility, count conflicts.

    Returns {compatible, warnings, tables}.
    """
    warnings: list[str] = []

    # Schema compatibility check
    import_version = import_data["metadata"].get("schema_version", "unknown")
    latest_version = (await db.execute(
        text("SELECT version FROM schema_versions ORDER BY applied_at DESC LIMIT 1")
    )).mappings().first()
    current_version = latest_version["version"] if latest_version else app_version
    compatible = True
    if import_version != current_version:
        warnings.append(
            f"Schema version mismatch: import={import_version}, current={current_version}"
        )

    tables_result = []
    for t_name, rows in import_data["data"].items():
        if t_name not in _EXPORTABLE_TABLES:
            warnings.append(f"Skipping non-exportable table: {t_name}")
            continue

        total = len(rows)
        new_count = 0
        conflict_count = 0

        if t_name == "articles":
            urls = [r.get("url") for r in rows if r.get("url")]
            if urls:
                existing_rows = (await db.execute(
                    text("SELECT url FROM articles WHERE url = ANY(:urls)"),
                    {"urls": urls},
                )).mappings().all()
                existing_urls = {r["url"] for r in existing_rows}
            else:
                existing_urls = set()
            for row in rows:
                url = row.get("url")
                if url:
                    if url in existing_urls:
                        conflict_count += 1
                    else:
                        new_count += 1
                else:
                    new_count += 1

        elif t_name == "sites":
            urls = [r.get("url") for r in rows if r.get("url")]
            if urls:
                existing_rows = (await db.execute(
                    text("SELECT url FROM sites WHERE url = ANY(:urls)"),
                    {"urls": urls},
                )).mappings().all()
                existing_site_urls = {r["url"] for r in existing_rows}
            else:
                existing_site_urls = set()
            for row in rows:
                url = row.get("url")
                if url:
                    if url in existing_site_urls:
                        conflict_count += 1
                    else:
                        new_count += 1
                else:
                    new_count += 1

        elif t_name == "users":
            emails = [r.get("email") for r in rows if r.get("email")]
            if emails:
                existing_rows = (await db.execute(
                    text("SELECT email FROM users WHERE email = ANY(:emails)"),
                    {"emails": emails},
                )).mappings().all()
                existing_emails = {r["email"] for r in existing_rows}
            else:
                existing_emails = set()
            for row in rows:
                email = row.get("email")
                if email:
                    if email in existing_emails:
                        conflict_count += 1
                    else:
                        new_count += 1
                else:
                    new_count += 1

        elif t_name == "roles":
            names = [r.get("name") for r in rows if r.get("name")]
            if names:
                existing_rows = (await db.execute(
                    text("SELECT name FROM roles WHERE name = ANY(:names)"),
                    {"names": names},
                )).mappings().all()
                existing_names = {r["name"] for r in existing_rows}
            else:
                existing_names = set()
            for row in rows:
                name = row.get("name")
                if name:
                    if name in existing_names:
                        conflict_count += 1
                    else:
                        new_count += 1
                else:
                    new_count += 1

        else:
            # crawl_attempts, rss_query_events, user_roles — no standalone unique key
            new_count = total

        tables_result.append({
            "name": t_name,
            "total": total,
            "new": new_count,
            "conflicts": conflict_count,
        })

    return {
        "compatible": compatible,
        "warnings": warnings,
        "tables": tables_result,
    }


async def execute_import(db, import_data: dict, mode: str) -> list[dict]:
    """Execute import with ID remapping. Returns per-table result list.

    Transaction wrapping is included here. Raises ValueError for unknown mode.
    """
    if mode not in ("skip", "overwrite"):
        raise ValueError("mode must be 'skip' or 'overwrite'")

    results = []

    # ID remapping: old export id -> new DB id
    site_id_map: dict[int, int] = {}
    role_id_map: dict[int, int] = {}
    user_id_map: dict[int, int] = {}

    async with db.begin():
        for t_name in _IMPORT_ORDER:
            if t_name not in import_data.get("data", {}):
                continue
            if t_name not in _EXPORTABLE_TABLES:
                continue

            rows = import_data["data"][t_name]
            tbl = _TABLE_MAP[t_name]
            valid_columns = {c.name for c in tbl.columns}

            imported = 0
            skipped = 0
            overwritten = 0

            for row in rows:
                old_id = row.get("id")

                # --- roles ---
                if t_name == "roles":
                    row_data = {
                        k: v for k, v in row.items()
                        if k != "id" and k in valid_columns
                    }
                    name = row.get("name")
                    existing = (
                        (await db.execute(
                            roles.select().where(roles.c.name == name)
                        )).mappings().first()
                        if name
                        else None
                    )
                    if existing:
                        if old_id is not None:
                            role_id_map[old_id] = existing["id"]
                        if mode == "skip":
                            skipped += 1
                        else:
                            update_vals = {}
                            if row_data.get("description") is not None:
                                update_vals["description"] = row_data["description"]
                            if update_vals:
                                await db.execute(
                                    roles.update()
                                    .where(roles.c.id == existing["id"])
                                    .values(**update_vals)
                                )
                            overwritten += 1
                    else:
                        result = await db.execute(
                            roles.insert().values(**row_data).returning(roles.c.id)
                        )
                        new_id = result.scalar()
                        if old_id is not None:
                            role_id_map[old_id] = new_id
                        imported += 1

                # --- users ---
                elif t_name == "users":
                    row_data = {
                        k: v for k, v in row.items()
                        if k != "id" and k in valid_columns
                    }
                    email = row.get("email")
                    existing = (
                        (await db.execute(
                            users.select().where(users.c.email == email)
                        )).mappings().first()
                        if email
                        else None
                    )
                    if existing:
                        if old_id is not None:
                            user_id_map[old_id] = existing["id"]
                        if mode == "skip":
                            skipped += 1
                        else:
                            update_vals = {}
                            for field in ("full_name", "status", "preferences", "password_hash"):
                                if field in row_data:
                                    update_vals[field] = row_data[field]
                            if update_vals:
                                now = datetime.now(timezone.utc)
                                update_vals["updated_at"] = now
                                await db.execute(
                                    users.update()
                                    .where(users.c.id == existing["id"])
                                    .values(**update_vals)
                                )
                            overwritten += 1
                    else:
                        # Ensure required derived fields exist
                        if "email_normalized" not in row_data and email:
                            row_data["email_normalized"] = normalize_email(email)
                        if "username_normalized" not in row_data and row_data.get("username"):
                            row_data["username_normalized"] = normalize_username(row_data["username"])
                        if "avatar_source" not in row_data:
                            row_data["avatar_source"] = "none"
                        if "preferences" not in row_data:
                            row_data["preferences"] = {}
                        if "status" not in row_data:
                            row_data["status"] = "active"
                        now = datetime.now(timezone.utc)
                        if "created_at" not in row_data:
                            row_data["created_at"] = now
                        if "updated_at" not in row_data:
                            row_data["updated_at"] = now
                        result = await db.execute(
                            users.insert().values(**row_data).returning(users.c.id)
                        )
                        new_id = result.scalar()
                        if old_id is not None:
                            user_id_map[old_id] = new_id
                        imported += 1

                # --- user_roles ---
                elif t_name == "user_roles":
                    old_user_id = row.get("user_id")
                    old_role_id = row.get("role_id")
                    new_user_id = user_id_map.get(old_user_id) if old_user_id is not None else None
                    new_role_id = role_id_map.get(old_role_id) if old_role_id is not None else None
                    if new_user_id is None or new_role_id is None:
                        skipped += 1
                        continue
                    existing = (await db.execute(
                        user_roles.select().where(
                            (user_roles.c.user_id == new_user_id) &
                            (user_roles.c.role_id == new_role_id)
                        )
                    )).mappings().first()
                    if existing:
                        skipped += 1
                    else:
                        await db.execute(
                            user_roles.insert().values(user_id=new_user_id, role_id=new_role_id)
                        )
                        imported += 1

                # --- sites ---
                elif t_name == "sites":
                    row_data = {
                        k: v for k, v in row.items()
                        if k != "id" and k in valid_columns
                    }
                    url = row.get("url")
                    existing = (
                        (await db.execute(
                            sites.select().where(sites.c.url == url)
                        )).mappings().first()
                        if url
                        else None
                    )
                    if existing:
                        if old_id is not None:
                            site_id_map[old_id] = existing["id"]
                        if mode == "skip":
                            skipped += 1
                        else:
                            await db.execute(
                                sites.update()
                                .where(sites.c.id == existing["id"])
                                .values(**row_data)
                            )
                            overwritten += 1
                    else:
                        result = await db.execute(
                            sites.insert().values(**row_data).returning(sites.c.id)
                        )
                        new_id = result.scalar()
                        if old_id is not None:
                            site_id_map[old_id] = new_id
                        imported += 1

                # --- articles ---
                elif t_name == "articles":
                    row_data = {
                        k: v for k, v in row.items()
                        if k != "id" and k in valid_columns
                    }
                    old_site_id = row_data.get("site_id")
                    if old_site_id is not None and old_site_id in site_id_map:
                        row_data["site_id"] = site_id_map[old_site_id]
                    url = row.get("url")
                    existing = (
                        (await db.execute(
                            articles.select().where(articles.c.url == url)
                        )).mappings().first()
                        if url
                        else None
                    )
                    if existing:
                        if mode == "skip":
                            skipped += 1
                        else:
                            await db.execute(
                                articles.update()
                                .where(articles.c.id == existing["id"])
                                .values(**row_data)
                            )
                            overwritten += 1
                    else:
                        await db.execute(
                            articles.insert().values(**row_data)
                        )
                        imported += 1

                else:
                    # crawl_attempts, rss_query_events — always insert, remap site_id
                    row_data = {
                        k: v for k, v in row.items()
                        if k != "id" and k in valid_columns
                    }
                    old_site_id = row_data.get("site_id")
                    if old_site_id is not None and old_site_id in site_id_map:
                        row_data["site_id"] = site_id_map[old_site_id]
                    await db.execute(tbl.insert().values(**row_data))
                    imported += 1

            results.append({
                "name": t_name,
                "imported": imported,
                "skipped": skipped,
                "overwritten": overwritten,
            })

    return results


# ---------------------------------------------------------------------------
# Status service function
# ---------------------------------------------------------------------------

async def compute_database_status(db, app_migrations: list, app_version: str) -> dict:
    """Compute database status: schema version, table counts, pending migrations.

    app_migrations is the MIGRATIONS list from the router.
    app_version is APP_VERSION from the router.
    """
    # Current schema version
    latest_version = (await db.execute(
        text("SELECT version, applied_at FROM schema_versions ORDER BY applied_at DESC LIMIT 1")
    )).mappings().first()
    current_version = latest_version["version"] if latest_version else "unknown"
    last_migration_at = (
        latest_version["applied_at"].isoformat()
        if latest_version and latest_version["applied_at"]
        else None
    )

    # Table row counts (exclude system tables) — run all COUNTs in parallel
    table_names = [
        t.name for t in metadata.sorted_tables if t.name not in _SYSTEM_TABLES
    ]

    async def _count_table(name: str) -> dict:
        try:
            row = (await db.execute(
                text(f'SELECT COUNT(*) AS cnt FROM "{name}"')
            )).mappings().first()
            return {"name": name, "row_count": row["cnt"] if row else 0}
        except Exception:
            return {"name": name, "row_count": -1}

    tables_info = list(await asyncio.gather(*[_count_table(n) for n in table_names]))

    # Pending migrations
    applied_rows = (await db.execute(schema_versions.select())).mappings().all()
    applied_versions = {r["version"] for r in applied_rows}
    pending = [
        {"version": m["version"], "description": m["description"]}
        for m in app_migrations
        if m["version"] not in applied_versions
    ]

    return {
        "schema_version": current_version,
        "app_version": app_version,
        "tables": tables_info,
        "pending_migrations": pending,
        "last_migration_at": last_migration_at,
    }
