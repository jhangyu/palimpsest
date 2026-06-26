"""
---
name: ownership
description: "Feed ownership authorization: site ownership checks, ownership transfer gate, and owner status queries"
type: core
target:
  layer: backend
  domain: auth
spec_doc: null
test_file: tests/stage1/test_site_ownership.py
functions:
  - name: check_site_owner_or_admin
    line: 7
    purpose: "Pure function: returns True if user owns the site or is admin"
  - name: ownership_transfer_gate
    line: 20
    purpose: "Return sites owned by user_id; non-empty blocks delete/block operations"
  - name: get_sites_with_owner_status
    line: 35
    purpose: "Return all sites joined with their owner's account status"
  - name: verify_transfer_target
    line: 52
    purpose: "Verify new owner exists and is active before ownership transfer"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
from __future__ import annotations

import sqlalchemy


def check_site_owner_or_admin(site_row, user_id: int, is_admin: bool) -> bool:
    """Pure function: returns True if user owns the site or is admin.

    Legacy sites with NULL owner_user_id are treated as admin-only.
    """
    if is_admin:
        return True
    owner = site_row["owner_user_id"]
    if owner is None:
        return False
    return owner == user_id


async def ownership_transfer_gate(db, user_id: int) -> list[dict]:
    """Returns list of sites owned by user_id.

    Non-empty result means the user cannot be deleted or blocked
    until ownership is transferred.
    """
    rows = (await db.execute(
        sqlalchemy.text(
            "SELECT id, name, url FROM sites WHERE owner_user_id = :user_id"
        ),
        {"user_id": user_id},
    )).mappings().all()
    return [dict(row) for row in rows]


async def get_sites_with_owner_status(db) -> list[dict]:
    """Returns all sites joined with their owner's account status.

    Each row includes all site fields plus:
    - owner_status: the owner's status value ('active', 'blocked', etc.) or NULL for unowned sites
    - owner_user_id: the owning user's id or NULL

    The ``s.*`` wildcard automatically includes all sites columns, including
    the RSS-related columns added by migration: ``source_type``,
    ``rss_full_content``, and ``website_url``.  The scheduler uses these to
    pass the correct parameters to ``crawl_site_logic()``.
    """
    rows = (await db.execute(
        sqlalchemy.text(
            "SELECT s.*, u.status AS owner_status "
            "FROM sites s "
            "LEFT JOIN users u ON u.id = s.owner_user_id"
        )
    )).mappings().all()
    return [dict(row) for row in rows]


async def verify_transfer_target(db, new_owner_id: int) -> dict | None:
    """Verify new owner exists and is active.

    Returns the user row (id, email, status) or None if not found / not active.
    """
    row = (await db.execute(
        sqlalchemy.text(
            "SELECT id, email, status FROM users "
            "WHERE id = :new_owner_id AND status = 'active'"
        ),
        {"new_owner_id": new_owner_id},
    )).mappings().first()
    return dict(row) if row else None
