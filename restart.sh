#!/bin/bash

# Stop existing servers
echo "Stopping existing servers..."
lsof -ti:8088 | xargs kill -9 2>/dev/null
lsof -ti:5174 | xargs kill -9 2>/dev/null
sleep 2

# Get project directory
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$PROJECT_DIR/log/runtime"
mkdir -p "$LOG_DIR"

# Start backend
echo "Starting backend..."
cd "$PROJECT_DIR/backend"
source ../.venv/bin/activate
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8088 > "$LOG_DIR/backend-server.log" 2>&1 &
BACKEND_PID=$!
echo "Backend started (PID: $BACKEND_PID)"

# Start frontend - Astro (on 5174)
echo "Starting frontend (Astro on 5174)..."
cd "$PROJECT_DIR/frontend-astro"
export NODE_ENV=development
npm install --ignore-scripts 2>/dev/null
nohup npm run dev > "$LOG_DIR/frontend-astro.log" 2>&1 &
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
