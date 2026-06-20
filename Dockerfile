# =============================================================================
# Palimpsest — Multi-stage Docker build
# Stage 1: Build frontend assets (node:20-bookworm-slim)
# Stage 2: Runtime image       (python:3.11-slim-bookworm)
# =============================================================================

# ── Stage 1: Frontend builder ─────────────────────────────────────────────────
FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend-astro

# Copy manifests first — only re-runs npm ci when lock file changes
COPY frontend-astro/package*.json ./
RUN npm ci

COPY frontend-astro ./
RUN npm run build

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="Palimpsest" \
      org.opencontainers.image.version="0.1.1" \
      org.opencontainers.image.description="AI-powered full-text RSS content management system" \
      org.opencontainers.image.source="https://github.com/jhangyu/palimpsest" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PALIMPSEST_FRONTEND_DIR=/app/frontend \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    PYTHONPATH=/app/backend/playwright_stub

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies before copying app code — maximises cache reuse
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt \
    && { pip uninstall -y pip setuptools wheel 2>/dev/null || true; }

# Copy application code and built frontend assets
COPY backend /app/backend
COPY --from=frontend-builder /app/frontend-astro/dist /app/frontend
COPY --chmod=755 entrypoint.sh /app/entrypoint.sh

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8088/health', timeout=5).read()"

ENTRYPOINT ["/app/entrypoint.sh"]
