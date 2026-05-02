FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /app/frontend-astro

COPY frontend-astro/package*.json ./
RUN npm ci --omit=dev

COPY frontend-astro ./
RUN npm run build

FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PALIMPSEST_FRONTEND_DIR=/app/frontend

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY --from=frontend-builder /app/frontend-astro/dist /app/frontend
COPY --chmod=755 entrypoint.sh /app/entrypoint.sh

EXPOSE 8088

ENTRYPOINT ["/app/entrypoint.sh"]
