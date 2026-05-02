#!/usr/bin/env bash
set -euo pipefail

APP_HOST="${APP_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8088}"

wait_for_tcp() {
  local host="$1"
  local port="$2"
  local name="$3"
  local attempts="${4:-60}"

  echo "Waiting for ${name} at ${host}:${port}..."
  for _ in $(seq 1 "${attempts}"); do
    if timeout 1 bash -c "cat < /dev/null > /dev/tcp/${host}/${port}" 2>/dev/null; then
      echo "${name} is ready."
      return 0
    fi
    sleep 1
  done

  echo "Timed out waiting for ${name} at ${host}:${port}." >&2
  return 1
}

shutdown() {
  echo "Shutting down palimpsest..."
  if [[ -n "${BACKEND_PID:-}" ]]; then
    kill "${BACKEND_PID}" 2>/dev/null || true
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
}
trap shutdown SIGINT SIGTERM

if [[ "${WAIT_FOR_DB:-true}" == "true" ]]; then
  wait_for_tcp "${POSTGRES_HOST:-db}" "${POSTGRES_PORT:-5432}" "PostgreSQL"
fi

if [[ "${CHROME_MODE:-server}" != "local" && "${WAIT_FOR_CHROME:-true}" == "true" ]]; then
  wait_for_tcp "${CHROME_HOST:-chrome}" "${CHROME_PORT:-3000}" "Browserless Chrome"
fi

echo "Starting backend on ${APP_HOST}:${BACKEND_PORT}..."
cd /app/backend
python -m uvicorn main:app --host "${APP_HOST}" --port "${BACKEND_PORT}" &
BACKEND_PID=$!

echo "palimpsest is running:"
echo "- App and API: http://localhost:${BACKEND_PORT}"

set +e
wait "${BACKEND_PID}"
EXIT_CODE=$?
echo "palimpsest exited with code ${EXIT_CODE}."
exit "${EXIT_CODE}"
