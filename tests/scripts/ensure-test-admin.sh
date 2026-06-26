#!/usr/bin/env bash
# ensure-test-admin.sh
# Ensures the test admin user exists in the test DB with the correct password and roles.
# Safe to run multiple times (idempotent).
#
# Usage: bash tests/scripts/ensure-test-admin.sh
#        (or source tests/scripts/test-env.sh first, then run)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# 1. Source test-env.sh
# ---------------------------------------------------------------------------
if [[ -f "${SCRIPT_DIR}/test-env.sh" ]]; then
    # shellcheck source=./test-env.sh
    source "${SCRIPT_DIR}/test-env.sh"
    echo "[INFO] Sourced test-env.sh"
else
    echo "[ERROR] Cannot find test-env.sh at ${SCRIPT_DIR}/test-env.sh" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# 2. Check required env vars
# ---------------------------------------------------------------------------
if [[ -z "${TEST_DATABASE_URL:-}" ]]; then
    echo "[ERROR] TEST_DATABASE_URL is not set" >&2
    exit 1
fi

if [[ -z "${TEST_ADMIN_EMAIL:-}" ]]; then
    echo "[ERROR] TEST_ADMIN_EMAIL is not set" >&2
    exit 1
fi

if [[ -z "${TEST_ADMIN_PASSWORD:-}" ]]; then
    echo "[ERROR] TEST_ADMIN_PASSWORD is not set" >&2
    exit 1
fi

echo "[INFO] TEST_DATABASE_URL=${TEST_DATABASE_URL}"
echo "[INFO] TEST_ADMIN_EMAIL=${TEST_ADMIN_EMAIL}"

# ---------------------------------------------------------------------------
# 3. Check test DB is reachable (port 5433)
# ---------------------------------------------------------------------------
echo "[INFO] Checking test DB connectivity on port 5433..."

if command -v pg_isready &>/dev/null; then
    if ! pg_isready -h localhost -p 5433 -U palimpsest -d palimpsest_test -q; then
        echo "[ERROR] Test DB not reachable at localhost:5433 (pg_isready failed)" >&2
        echo "[HINT]  Start the test DB with: docker-compose -f docker-compose.test.yml up -d db-test" >&2
        exit 1
    fi
    echo "[OK] Test DB is reachable (pg_isready)"
else
    # Fallback: try psql
    if command -v psql &>/dev/null; then
        if ! psql "${TEST_DATABASE_URL}" -c "SELECT 1;" &>/dev/null; then
            echo "[ERROR] Test DB not reachable at localhost:5433 (psql failed)" >&2
            echo "[HINT]  Start the test DB with: docker-compose -f docker-compose.test.yml up -d db-test" >&2
            exit 1
        fi
        echo "[OK] Test DB is reachable (psql)"
    else
        echo "[WARN] Neither pg_isready nor psql found — skipping connectivity check" >&2
    fi
fi

# ---------------------------------------------------------------------------
# 4. Create / verify admin user via inline Python
# ---------------------------------------------------------------------------
echo "[INFO] Ensuring admin user exists in test DB..."

python3 - <<'PYEOF'
import sys
import os
import re
from datetime import datetime, timezone

# --- Import dependencies ---
try:
    import psycopg2
except ImportError:
    print("[ERROR] psycopg2 not installed. Run: pip install psycopg2-binary", file=sys.stderr)
    sys.exit(1)

try:
    from argon2 import PasswordHasher, Type as Argon2Type
    from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
except ImportError:
    print("[ERROR] argon2-cffi not installed. Run: pip install argon2-cffi", file=sys.stderr)
    sys.exit(1)

# --- Read env ---
db_url = os.environ["TEST_DATABASE_URL"]
email = os.environ["TEST_ADMIN_EMAIL"]
password = os.environ["TEST_ADMIN_PASSWORD"]

# --- Parse postgresql://user:pass@host:port/dbname ---
m = re.match(
    r"postgresql://([^:]+):([^@]+)@([^:/]+):(\d+)/(.+)",
    db_url,
)
if not m:
    print(f"[ERROR] Cannot parse TEST_DATABASE_URL: {db_url}", file=sys.stderr)
    sys.exit(1)

db_user, db_pass, db_host, db_port, db_name = m.groups()

# --- Argon2id hasher (same params as backend/core/auth.py) ---
_ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=1,
    hash_len=32,
    type=Argon2Type.ID,  # Argon2id
)

# --- Connect ---
try:
    conn = psycopg2.connect(
        host=db_host,
        port=int(db_port),
        dbname=db_name,
        user=db_user,
        password=db_pass,
    )
    conn.autocommit = False
except Exception as exc:
    print(f"[ERROR] DB connection failed: {exc}", file=sys.stderr)
    sys.exit(1)

now = datetime.now(timezone.utc)
email_normalized = email.lower().strip()
# Username for test admin; must be 1-20 lowercase letters and not reserved
# Using "testadmin" avoids the reserved word "admin"
username = "testadmin"
username_normalized = username.lower()

try:
    with conn.cursor() as cur:

        # ----------------------------------------------------------------
        # Upsert user
        # ----------------------------------------------------------------
        cur.execute(
            "SELECT id, password_hash FROM users WHERE email_normalized = %s",
            (email_normalized,),
        )
        row = cur.fetchone()

        if row is None:
            # Generate password hash
            password_hash = _ph.hash(password)

            cur.execute(
                """
                INSERT INTO users (
                    email, email_normalized,
                    username, username_normalized,
                    full_name, password_hash, status,
                    email_verified_at,
                    avatar_source, preferences,
                    created_at, updated_at
                ) VALUES (
                    %s, %s,
                    %s, %s,
                    %s, %s, 'active',
                    %s,
                    'none', '{}',
                    %s, %s
                ) RETURNING id
                """,
                (
                    email, email_normalized,
                    username, username_normalized,
                    "Test Admin",
                    password_hash,
                    now,  # email_verified_at
                    now, now,
                ),
            )
            user_id = cur.fetchone()[0]
            print(f"[OK] Created user '{email}' with id={user_id}")

        else:
            user_id, existing_hash = row[0], row[1]
            # Verify password; update if mismatch
            try:
                _ph.verify(existing_hash, password)
                print(f"[OK] User '{email}' already exists with correct password hash")
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                new_hash = _ph.hash(password)
                cur.execute(
                    "UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s",
                    (new_hash, now, user_id),
                )
                print(f"[UPDATED] User '{email}' password hash updated")

        # ----------------------------------------------------------------
        # Ensure roles exist and are assigned
        # ----------------------------------------------------------------
        for role_name in ("admin", "user"):
            # Get or create role
            cur.execute("SELECT id FROM roles WHERE name = %s", (role_name,))
            role_row = cur.fetchone()
            if role_row is None:
                cur.execute(
                    "INSERT INTO roles (name, description, created_at) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (role_name, f"Built-in {role_name} role", now),
                )
                role_id = cur.fetchone()[0]
                print(f"[OK] Created role '{role_name}' with id={role_id}")
            else:
                role_id = role_row[0]

            # Assign role if not already present
            cur.execute(
                "SELECT 1 FROM user_roles WHERE user_id = %s AND role_id = %s",
                (user_id, role_id),
            )
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)",
                    (user_id, role_id),
                )
                print(f"[OK] Assigned role '{role_name}' to user '{email}'")
            else:
                print(f"[OK] User '{email}' already has role '{role_name}'")

        conn.commit()
        print("[SUCCESS] Admin user setup complete")

except Exception as exc:
    conn.rollback()
    print(f"[ERROR] DB operation failed: {exc}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    conn.close()
PYEOF

echo "[INFO] ensure-test-admin.sh finished successfully"
