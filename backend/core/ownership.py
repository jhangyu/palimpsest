"""Feed ownership authorization helpers."""
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
    rows = await db.fetch_all(
        sqlalchemy.text(
            "SELECT id, name, url FROM sites WHERE owner_user_id = :user_id"
        ),
        {"user_id": user_id},
    )
    return [dict(row) for row in rows]


async def get_sites_with_owner_status(db) -> list[dict]:
    """Returns all sites joined with their owner's account status.

    Each row includes all site fields plus:
    - owner_status: the owner's status value ('active', 'blocked', etc.) or NULL for unowned sites
    - owner_user_id: the owning user's id or NULL
    """
    rows = await db.fetch_all(
        sqlalchemy.text(
            "SELECT s.*, u.status AS owner_status "
            "FROM sites s "
            "LEFT JOIN users u ON u.id = s.owner_user_id"
        )
    )
    return [dict(row) for row in rows]


async def verify_transfer_target(db, new_owner_id: int) -> dict | None:
    """Verify new owner exists and is active.

    Returns the user row (id, email, status) or None if not found / not active.
    """
    row = await db.fetch_one(
        sqlalchemy.text(
            "SELECT id, email, status FROM users "
            "WHERE id = :new_owner_id AND status = 'active'"
        ),
        {"new_owner_id": new_owner_id},
    )
    return dict(row) if row else None
