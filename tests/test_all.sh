#!/usr/bin/env bash
# Palimpsest Test Suite -- Master Runner
# Runs all three stages in order with stage gates.
# Usage: bash tests/test_all.sh
set -euo pipefail

# === Preflight: ensure test environment and admin user ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$REPO_ROOT/tests/scripts/test-env.sh"

echo "=== Preflight: Ensuring test admin user exists in test DB ==="
if ! bash "$REPO_ROOT/tests/scripts/ensure-test-admin.sh"; then
    echo "FATAL: Preflight check failed. Aborting tests."
    exit 1
fi
echo "=== Preflight: PASSED ==="

echo "========================================"
echo "  Palimpsest Test Suite"
echo "========================================"

# ---------------------------------------------------------------------------
# DB cleanup helper (truncates test tables)
# ---------------------------------------------------------------------------
db_cleanup() {
    PYTHONPATH=".:backend:tests/stage1" python -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def cleanup():
    engine = create_async_engine('${TEST_DATABASE_URL}')
    async with engine.begin() as conn:
        for t in ['rss_query_events','articles','crawl_repair_attempts','crawl_repair_states','sites','ai_providers','sessions','users']:
            try:
                await conn.execute(text(f'DELETE FROM {t}'))
            except Exception:
                pass
    await engine.dispose()
asyncio.run(cleanup())
print('Test DB cleaned.')
" 2>/dev/null || echo "DB cleanup skipped"
}

# Register EXIT trap for post-test cleanup
cleanup_on_exit() {
    echo ""
    echo "--- Post-test: Clean test database ---"
    db_cleanup
}
trap cleanup_on_exit EXIT

# ---------------------------------------------------------------------------
# Pre-test: clean the test database
# ---------------------------------------------------------------------------
echo ""
echo "--- Pre-test: Clean test database ---"
db_cleanup

# ---------------------------------------------------------------------------
# Stage 1: Pytest API Tests
# ---------------------------------------------------------------------------
echo ""
echo "=== Stage 1: Pytest API Tests ==="
TEST_DATABASE_URL="${TEST_DATABASE_URL}" \
PYTHONPATH=".:backend:tests/stage1" \
python -m pytest tests/stage1/ -v --tb=short -x
echo ""
echo "[PASS] Stage 1 PASSED"

# ---------------------------------------------------------------------------
# Stage 2: Local Integration Tests (curl)
# ---------------------------------------------------------------------------
echo ""
echo "=== Stage 2: Integration Tests (curl) ==="
bash tests/stage2/integration/test_stage2_integration.sh "${BASE_URL:-http://localhost:8088}"
echo ""
echo "[PASS] Stage 2 PASSED"

# ---------------------------------------------------------------------------
# Stage 3: Docker Compose Integration Tests
# ---------------------------------------------------------------------------
echo ""
echo "=== Stage 3: Docker Integration Tests ==="
echo "--- Building Docker image for Stage 3 ---"
docker build -t palimpsest:test -f Dockerfile . || echo "[WARN] Docker build failed"
export IMAGE_TAG="palimpsest:test"
bash tests/stage3/test_stage3_docker.sh
echo ""
echo "[PASS] Stage 3 PASSED"

echo ""
echo "========================================"
echo "  ALL STAGES PASSED"
echo "========================================"
