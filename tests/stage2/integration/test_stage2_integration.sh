#!/usr/bin/env bash
# Stage 2: Local Integration Tests
# Usage: bash tests/test_stage2_integration.sh [BASE_URL]
# Default BASE_URL: http://localhost:8088

set -euo pipefail

# === Preflight: ensure test environment and admin user ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

if [[ -z "${TEST_ADMIN_EMAIL:-}" ]]; then
    source "$REPO_ROOT/tests/scripts/test-env.sh"
    echo "=== Preflight: Ensuring test admin user exists in test DB ==="
    if ! bash "$REPO_ROOT/tests/scripts/ensure-test-admin.sh"; then
        echo "FATAL: Preflight check failed. Aborting tests."
        exit 1
    fi
    echo "=== Preflight: PASSED ==="
else
    echo "=== Preflight: Skipped (TEST_ADMIN_EMAIL already set by parent) ==="
fi

# macOS BSD head does not support `head -n -1`; use sed instead
strip_last_line() { sed '$d'; }

BASE_URL="${1:-http://localhost:8088}"
COOKIE_JAR=$(mktemp)
PASS=0
FAIL=0
TOTAL=14

# Track created resources for cleanup
SITE_ID=""
PROVIDER_ID=""

cleanup() {
    # Best-effort API cleanup of test-created data
    if [ -f "$COOKIE_JAR" ]; then
        local cleanup_jar
        cleanup_jar=$(mktemp)
        curl -s -X POST "$BASE_URL/auth/login" \
            -H "Content-Type: application/json" \
            -d "{\"email\":\"$TEST_ADMIN_EMAIL\",\"password\":\"$TEST_ADMIN_PASSWORD\"}" \
            -c "$cleanup_jar" -o /dev/null 2>/dev/null || true
        local cleanup_csrf
        cleanup_csrf=$(grep "csrf_token" "$cleanup_jar" 2>/dev/null | awk '{print $NF}' || true)
        if [ -n "$SITE_ID" ] && [ "$SITE_ID" != "null" ]; then
            curl -s -X DELETE "$BASE_URL/sites/$SITE_ID" \
                -H "X-CSRF-Token: $cleanup_csrf" \
                -b "$cleanup_jar" -o /dev/null 2>/dev/null || true
        fi
        if [ -n "$PROVIDER_ID" ] && [ "$PROVIDER_ID" != "null" ]; then
            curl -s -X DELETE "$BASE_URL/settings/ai-providers/$PROVIDER_ID" \
                -H "Content-Type: application/json" \
                -H "X-CSRF-Token: $cleanup_csrf" \
                -b "$cleanup_jar" \
                -d '{"revision":1}' -o /dev/null 2>/dev/null || true
        fi
        rm -f "$cleanup_jar"
    fi
    rm -f "$COOKIE_JAR"
}
trap cleanup EXIT

pass() { echo "  [PASS] $1"; PASS=$((PASS+1)); }
fail() { echo "  [FAIL] $1: $2"; FAIL=$((FAIL+1)); }

assert_status() {
    local expected=$1 actual=$2 test_name=$3
    if [ "$actual" -eq "$expected" ]; then
        pass "$test_name"
    else
        fail "$test_name" "expected HTTP $expected, got $actual"
    fi
}

# ---------------------------------------------------------------------------
# 2.1 Health Check
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.1 Health Check ---"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health")
assert_status 200 "$STATUS" "GET /health returns 200"

# ---------------------------------------------------------------------------
# 2.2 First-Run Check
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.2 First-Run Check ---"
BODY=$(curl -s "$BASE_URL/auth/first-run-check")
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/auth/first-run-check")
assert_status 200 "$STATUS" "GET /auth/first-run-check returns 200"
if echo "$BODY" | grep -q '"needs_setup"'; then
    pass "first-run-check response contains needs_setup field"
else
    fail "first-run-check response format" "missing needs_setup in: $BODY"
fi

# ---------------------------------------------------------------------------
# 2.3 First-Run Setup
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.3 First-Run Setup ---"
SETUP_BODY=$(curl -s -X POST "$BASE_URL/auth/first-run-setup" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$TEST_ADMIN_EMAIL\",\"username\":\"testadmin\",\"password\":\"$TEST_ADMIN_PASSWORD\",\"full_name\":\"Admin\"}" \
    -c "$COOKIE_JAR" \
    -w "\n%{http_code}")
SETUP_STATUS=$(echo "$SETUP_BODY" | tail -1)
SETUP_RESP=$(echo "$SETUP_BODY" | strip_last_line)

if [ "$SETUP_STATUS" -eq 200 ]; then
    pass "POST /auth/first-run-setup returns 200"
elif [ "$SETUP_STATUS" -eq 409 ]; then
    # Already set up — re-login to get cookies
    pass "POST /auth/first-run-setup (already done, proceeding with login)"
    LOGIN_BODY=$(curl -s -X POST "$BASE_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"email\":\"$TEST_ADMIN_EMAIL\",\"password\":\"$TEST_ADMIN_PASSWORD\"}" \
        -c "$COOKIE_JAR" \
        -w "\n%{http_code}")
    LOGIN_STATUS=$(echo "$LOGIN_BODY" | tail -1)
    if [ "$LOGIN_STATUS" -ne 200 ]; then
        fail "fallback login after 409" "HTTP $LOGIN_STATUS"
    fi
else
    fail "POST /auth/first-run-setup" "expected 200 or 409, got $SETUP_STATUS"
fi

# Verify cookies are saved
if grep -q "session_token" "$COOKIE_JAR"; then
    pass "session_token cookie set in cookie jar"
else
    fail "session_token cookie" "not found in cookie jar"
fi
if grep -q "csrf_token" "$COOKIE_JAR"; then
    pass "csrf_token cookie set in cookie jar"
else
    fail "csrf_token cookie" "not found in cookie jar"
fi

# Extract CSRF token
CSRF=$(grep "csrf_token" "$COOKIE_JAR" | awk '{print $NF}')

# ---------------------------------------------------------------------------
# 2.4 Auth Session (GET /auth/me)
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.4 Auth Session ---"
ME_BODY=$(curl -s -X GET "$BASE_URL/auth/me" \
    -b "$COOKIE_JAR" \
    -w "\n%{http_code}")
ME_STATUS=$(echo "$ME_BODY" | tail -1)
ME_RESP=$(echo "$ME_BODY" | strip_last_line)
assert_status 200 "$ME_STATUS" "GET /auth/me with session cookie returns 200"
if echo "$ME_RESP" | grep -q '"email"'; then
    pass "GET /auth/me response contains email field"
else
    fail "GET /auth/me response format" "missing email in: $ME_RESP"
fi

# ---------------------------------------------------------------------------
# 2.5 Login (re-login to refresh cookies)
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.5 Login ---"
LOGIN_BODY=$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$TEST_ADMIN_EMAIL\",\"password\":\"$TEST_ADMIN_PASSWORD\"}" \
    -c "$COOKIE_JAR" \
    -b "$COOKIE_JAR" \
    -w "\n%{http_code}")
LOGIN_STATUS=$(echo "$LOGIN_BODY" | tail -1)
assert_status 200 "$LOGIN_STATUS" "POST /auth/login returns 200"

# Refresh CSRF after login
CSRF=$(grep "csrf_token" "$COOKIE_JAR" | awk '{print $NF}')

# ---------------------------------------------------------------------------
# 2.6 AI Provider Create
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.6 AI Provider Create ---"
CREATE_PROV_BODY=$(curl -s -X POST "$BASE_URL/settings/ai-providers" \
    -H "Content-Type: application/json" \
    -H "X-CSRF-Token: $CSRF" \
    -b "$COOKIE_JAR" \
    -d '{"label":"Test Provider","protocol":"openai","base_url":"https://api.openai.com/v1","model":"gpt-4o","api_key":"sk-testkey1234567890abcdef","max_tokens":4096}' \
    -w "\n%{http_code}")
CREATE_PROV_STATUS=$(echo "$CREATE_PROV_BODY" | tail -1)
CREATE_PROV_RESP=$(echo "$CREATE_PROV_BODY" | strip_last_line)
assert_status 201 "$CREATE_PROV_STATUS" "POST /settings/ai-providers returns 201"

# Extract provider ID
if command -v jq &>/dev/null; then
    PROVIDER_ID=$(echo "$CREATE_PROV_RESP" | jq -r '.id // empty')
else
    PROVIDER_ID=$(echo "$CREATE_PROV_RESP" | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')
fi

if [ -n "$PROVIDER_ID" ] && [ "$PROVIDER_ID" != "null" ]; then
    pass "AI provider ID extracted: $PROVIDER_ID"
else
    fail "AI provider ID extraction" "could not extract id from: $CREATE_PROV_RESP"
    PROVIDER_ID="1"
fi

# Verify masked key
if echo "$CREATE_PROV_RESP" | grep -q "api_key_mask\|api_key_last4"; then
    pass "AI provider response contains masked key field"
else
    fail "AI provider key masking" "missing api_key_mask in response"
fi

# ---------------------------------------------------------------------------
# 2.7 AI Provider List
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.7 AI Provider List ---"
LIST_PROV_BODY=$(curl -s -X GET "$BASE_URL/settings/ai-providers" \
    -b "$COOKIE_JAR" \
    -w "\n%{http_code}")
LIST_PROV_STATUS=$(echo "$LIST_PROV_BODY" | tail -1)
LIST_PROV_RESP=$(echo "$LIST_PROV_BODY" | strip_last_line)
assert_status 200 "$LIST_PROV_STATUS" "GET /settings/ai-providers returns 200"
if echo "$LIST_PROV_RESP" | grep -q '"providers"'; then
    pass "GET /settings/ai-providers response has providers field"
else
    fail "GET /settings/ai-providers response format" "missing providers key"
fi
if echo "$LIST_PROV_RESP" | grep -q "encrypted_api_key"; then
    fail "Provider list security" "encrypted_api_key leaked in list response"
else
    pass "encrypted_api_key not present in list response"
fi

# ---------------------------------------------------------------------------
# 2.8 AI Provider Update
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.8 AI Provider Update ---"
UPDATE_PROV_BODY=$(curl -s -X PUT "$BASE_URL/settings/ai-providers/$PROVIDER_ID" \
    -H "Content-Type: application/json" \
    -H "X-CSRF-Token: $CSRF" \
    -b "$COOKIE_JAR" \
    -d '{"revision":1,"label":"Updated Provider"}' \
    -w "\n%{http_code}")
UPDATE_PROV_STATUS=$(echo "$UPDATE_PROV_BODY" | tail -1)
UPDATE_PROV_RESP=$(echo "$UPDATE_PROV_BODY" | strip_last_line)
assert_status 200 "$UPDATE_PROV_STATUS" "PUT /settings/ai-providers/$PROVIDER_ID returns 200"
if echo "$UPDATE_PROV_RESP" | grep -q '"Updated Provider"'; then
    pass "Provider label updated correctly"
else
    fail "Provider label update" "label not updated in response: $UPDATE_PROV_RESP"
fi

# ---------------------------------------------------------------------------
# 2.9 AI Provider Delete
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.9 AI Provider Delete ---"
DELETE_PROV_BODY=$(curl -s -X DELETE "$BASE_URL/settings/ai-providers/$PROVIDER_ID" \
    -H "Content-Type: application/json" \
    -H "X-CSRF-Token: $CSRF" \
    -b "$COOKIE_JAR" \
    -d '{"revision":2}' \
    -w "\n%{http_code}")
DELETE_PROV_STATUS=$(echo "$DELETE_PROV_BODY" | tail -1)
assert_status 204 "$DELETE_PROV_STATUS" "DELETE /settings/ai-providers/$PROVIDER_ID returns 204"
# Mark as deleted so cleanup skips it
PROVIDER_ID=""

# ---------------------------------------------------------------------------
# 2.10 AI Provider Test Connection (optional — gated by TEST_REAL_API_KEY)
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.10 AI Provider Test Connection (optional) ---"
if [ -n "${TEST_REAL_API_KEY:-}" ]; then
    # Create a provider with the real API key first
    REAL_PROV_BODY=$(curl -s -X POST "$BASE_URL/settings/ai-providers" \
        -H "Content-Type: application/json" \
        -H "X-CSRF-Token: $CSRF" \
        -b "$COOKIE_JAR" \
        -d "{\"label\":\"Real Test\",\"protocol\":\"openai\",\"base_url\":\"https://api.openai.com/v1\",\"model\":\"gpt-4o\",\"api_key\":\"$TEST_REAL_API_KEY\",\"max_tokens\":100}" \
        -w "\n%{http_code}")
    REAL_PROV_STATUS=$(echo "$REAL_PROV_BODY" | tail -1)
    REAL_PROV_RESP=$(echo "$REAL_PROV_BODY" | strip_last_line)
    if [ "$REAL_PROV_STATUS" -eq 201 ]; then
        if command -v jq &>/dev/null; then
            REAL_PROV_ID=$(echo "$REAL_PROV_RESP" | jq -r '.id // empty')
        else
            REAL_PROV_ID=$(echo "$REAL_PROV_RESP" | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')
        fi
        TEST_CONN_BODY=$(curl -s -X POST "$BASE_URL/settings/ai-providers/$REAL_PROV_ID/test" \
            -H "X-CSRF-Token: $CSRF" \
            -b "$COOKIE_JAR" \
            -w "\n%{http_code}")
        TEST_CONN_STATUS=$(echo "$TEST_CONN_BODY" | tail -1)
        assert_status 200 "$TEST_CONN_STATUS" "POST /settings/ai-providers/test-connection returns 200"
        # Clean up
        curl -s -X DELETE "$BASE_URL/settings/ai-providers/$REAL_PROV_ID" \
            -H "Content-Type: application/json" \
            -H "X-CSRF-Token: $CSRF" \
            -b "$COOKIE_JAR" \
            -d '{"revision":1}' -o /dev/null
    else
        fail "Real provider creation for connection test" "HTTP $REAL_PROV_STATUS"
    fi
else
    echo "  [SKIP] TEST_REAL_API_KEY not set — skipping connection test"
    pass "AI provider test connection (skipped — no real API key)"
fi

# ---------------------------------------------------------------------------
# 2.11 Site Create
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.11 Site Create ---"
CREATE_SITE_BODY=$(curl -s -X POST "$BASE_URL/sites/" \
    -H "Content-Type: application/json" \
    -H "X-CSRF-Token: $CSRF" \
    -b "$COOKIE_JAR" \
    -d '{"site":{"url":"https://example.com","name":"TestSite","refresh_frequency":60},"rules":{"list_rules":{},"content_rules":{}}}' \
    -w "\n%{http_code}")
CREATE_SITE_STATUS=$(echo "$CREATE_SITE_BODY" | tail -1)
CREATE_SITE_RESP=$(echo "$CREATE_SITE_BODY" | strip_last_line)
assert_status 200 "$CREATE_SITE_STATUS" "POST /sites/ returns 200"

# Extract site ID
if command -v jq &>/dev/null; then
    SITE_ID=$(echo "$CREATE_SITE_RESP" | jq -r '.id // empty')
else
    SITE_ID=$(echo "$CREATE_SITE_RESP" | grep -o '"id":[0-9]*' | head -1 | grep -o '[0-9]*')
fi

if [ -n "$SITE_ID" ] && [ "$SITE_ID" != "null" ]; then
    pass "Site ID extracted: $SITE_ID"
else
    fail "Site ID extraction" "could not extract id from: $CREATE_SITE_RESP"
    SITE_ID="1"
fi

# ---------------------------------------------------------------------------
# 2.12 Site List
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.12 Site List ---"
LIST_SITE_BODY=$(curl -s -X GET "$BASE_URL/sites/" \
    -b "$COOKIE_JAR" \
    -w "\n%{http_code}")
LIST_SITE_STATUS=$(echo "$LIST_SITE_BODY" | tail -1)
LIST_SITE_RESP=$(echo "$LIST_SITE_BODY" | strip_last_line)
assert_status 200 "$LIST_SITE_STATUS" "GET /sites/ returns 200"
if echo "$LIST_SITE_RESP" | grep -q "TestSite"; then
    pass "Site list contains created site"
else
    fail "Site list content" "TestSite not found in: $LIST_SITE_RESP"
fi

# ---------------------------------------------------------------------------
# 2.13 Site Delete
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.13 Site Delete ---"
DELETE_SITE_BODY=$(curl -s -X DELETE "$BASE_URL/sites/$SITE_ID" \
    -H "X-CSRF-Token: $CSRF" \
    -b "$COOKIE_JAR" \
    -w "\n%{http_code}")
DELETE_SITE_STATUS=$(echo "$DELETE_SITE_BODY" | tail -1)
assert_status 200 "$DELETE_SITE_STATUS" "DELETE /sites/$SITE_ID returns 200"
# Mark as deleted so cleanup skips it
SITE_ID=""

# ---------------------------------------------------------------------------
# 2.14 Logout
# ---------------------------------------------------------------------------
echo ""
echo "--- 2.14 Logout ---"
LOGOUT_BODY=$(curl -s -X POST "$BASE_URL/auth/logout" \
    -H "X-CSRF-Token: $CSRF" \
    -b "$COOKIE_JAR" \
    -w "\n%{http_code}")
LOGOUT_STATUS=$(echo "$LOGOUT_BODY" | tail -1)
assert_status 200 "$LOGOUT_STATUS" "POST /auth/logout returns 200"

# Verify session is invalidated
ME_AFTER_BODY=$(curl -s -X GET "$BASE_URL/auth/me" \
    -b "$COOKIE_JAR" \
    -w "\n%{http_code}")
ME_AFTER_STATUS=$(echo "$ME_AFTER_BODY" | tail -1)
assert_status 401 "$ME_AFTER_STATUS" "GET /auth/me after logout returns 401"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo "  Stage 2 Results: $PASS/$TOTAL passed, $FAIL failed"
echo "========================================"
[ "$FAIL" -eq 0 ] || exit 1
