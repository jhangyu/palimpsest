# ---
# name: Dockerfile
# description: "Multi-stage build: Node.js 22 frontend builder, Python 3.13 runtime, uvicorn entrypoint"
# type: deployment
# target:
#   layer: infrastructure
#   domain: container
# spec_doc: null
# test_file: tests/stage3/test_stage3_docker.sh
# ---
# =============================================================================
# Palimpsest — Multi-stage Docker build
# Stage 1: frontend-deps    (cache npm dependencies)
# Stage 2: frontend-builder (build Astro assets from project sources)
# Stage 3: python-deps      (cache apt + pip dependencies)
# Stage 4: runtime          (copy application sources last)
# =============================================================================

# ── Stage 1: Frontend dependencies ────────────────────────────────────────────
FROM node:22-bookworm-slim AS frontend-deps

WORKDIR /app/frontend-astro

# Keep npm dependency installation independent from frontend source changes.
COPY frontend-astro/package*.json ./
RUN npm ci

# ── Stage 2: Frontend builder ─────────────────────────────────────────────────
FROM frontend-deps AS frontend-builder

# Project sources are copied only after node_modules is cached.
COPY frontend-astro ./
RUN npm run build

# ── Stage 3: Python/runtime dependencies ──────────────────────────────────────
FROM python:3.13-slim-bookworm AS python-deps

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

WORKDIR /app

# OS packages rarely change; keep them before Python dependencies and app code.
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Keep pip dependency installation independent from backend source changes.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt \
    && { pip uninstall -y pip setuptools wheel 2>/dev/null || true; }

# ── Stage 4: Runtime ──────────────────────────────────────────────────────────
FROM python-deps AS runtime

ARG PALIMPSEST_VERSION="0.1.8-e2e"

LABEL org.opencontainers.image.title="Palimpsest" \
      org.opencontainers.image.version="0.1.9" \
      org.opencontainers.image.description="AI-powered full-text RSS content management system" \
      org.opencontainers.image.source="https://github.com/jhangyu/palimpsest" \
      org.opencontainers.image.licenses="MIT"

ENV PALIMPSEST_VERSION=${PALIMPSEST_VERSION} \
    PALIMPSEST_FRONTEND_DIR=/app/frontend \
    PYTHONPATH=/app/backend/playwright_stub

# Copy application code last so normal code edits do not invalidate apt/pip/npm layers.
COPY backend /app/backend
COPY --from=frontend-builder /app/frontend-astro/dist /app/frontend
COPY --chmod=755 entrypoint.sh /app/entrypoint.sh

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8088/health', timeout=5).read()"

ENTRYPOINT ["/app/entrypoint.sh"]
