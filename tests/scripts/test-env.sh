#!/usr/bin/env bash
# Test environment variables — source this file before running tests
export TEST_ADMIN_EMAIL="admin@test.local"
export TEST_ADMIN_PASSWORD="TestPass123!"
export TEST_DATABASE_URL="postgresql://palimpsest:testpass123@localhost:5433/palimpsest_test"
export TEST_DATABASE_URL_ASYNC="postgresql+asyncpg://palimpsest:testpass123@localhost:5433/palimpsest_test"
# Also set the Playwright-expected env vars
export PLAYWRIGHT_TEST_EMAIL="${TEST_ADMIN_EMAIL}"
export PLAYWRIGHT_TEST_PASSWORD="${TEST_ADMIN_PASSWORD}"
# Docker Stage 3 uses a separate admin in its fresh container DB
export DOCKER_TEST_EMAIL="docker-admin@test.local"
