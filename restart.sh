#!/bin/bash

# Stop existing servers
echo "Stopping existing servers..."
lsof -ti:8088 | xargs kill -9 2>/dev/null
lsof -ti:5174 | xargs kill -9 2>/dev/null
sleep 2

# Get project directory
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_DIR/log/runtime"
PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
POSTGRES_CONTAINER="palimpsest-local-db"
mkdir -p "$LOG_DIR"

wait_for_tcp() {
  local host="$1"
  local port="$2"
  local name="$3"
  local attempts="${4:-30}"

  for _ in $(seq 1 "$attempts"); do
    if nc -z "$host" "$port" >/dev/null 2>&1; then
      echo "$name is ready."
      return 0
    fi
    sleep 1
  done

  echo "Timed out waiting for $name at $host:$port." >&2
  return 1
}

wait_for_http() {
  local url="$1"
  local name="$2"
  local attempts="${3:-30}"

  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "$name is ready."
      return 0
    fi
    sleep 1
  done

  echo "Timed out waiting for $name at $url." >&2
  return 1
}

if ! nc -z localhost 5432 >/dev/null 2>&1; then
  echo "Starting local PostgreSQL..."
  if docker ps -a --format '{{.Names}}' | grep -qx "$POSTGRES_CONTAINER"; then
    docker start "$POSTGRES_CONTAINER" >/dev/null
  else
    docker run -d \
      --name "$POSTGRES_CONTAINER" \
      -e POSTGRES_USER=palimpsest \
      -e POSTGRES_PASSWORD=palimpsest \
      -e POSTGRES_DB=palimpsest \
      -p 127.0.0.1:5432:5432 \
      -v "$PROJECT_DIR/data/postgres:/var/lib/postgresql/data" \
      postgres:15-alpine >/dev/null
  fi
fi

wait_for_tcp localhost 5432 "PostgreSQL"

# Start backend
echo "Starting backend..."
cd "$PROJECT_DIR/backend"
nohup "$PYTHON_BIN" -m uvicorn main:app --host 0.0.0.0 --port 8088 </dev/null > "$LOG_DIR/backend-server.log" 2>&1 &
BACKEND_PID=$!
echo "Backend started (PID: $BACKEND_PID)"
if ! wait_for_http "http://localhost:8088/health" "Backend"; then
  echo "Backend failed to become healthy. Last log lines:" >&2
  tail -n 80 "$LOG_DIR/backend-server.log" >&2
  exit 1
fi

# Start frontend - Astro (on 5174)
echo "Starting frontend (Astro on 5174)..."
cd "$PROJECT_DIR/frontend-astro"
export NODE_ENV=development
npm install --ignore-scripts 2>/dev/null
nohup npm run dev </dev/null > "$LOG_DIR/frontend-astro.log" 2>&1 &
ASTRO_PID=$!
echo "Astro frontend started (PID: $ASTRO_PID)"

sleep 3

echo ""
echo "=== Server Status ==="
echo "Backend API:     http://localhost:8088"
echo "Astro Frontend: http://localhost:5174"
echo ""
echo "Logs:"
echo "  Backend:      tail -f $LOG_DIR/backend-server.log"
echo "  Astro:        tail -f $LOG_DIR/frontend-astro.log"
