# palimpsest

palimpsest is an AI-assisted RSS feed generator. It crawls dynamic web pages, asks an LLM to infer list/content selectors, extracts article content, stores results, and serves standard RSS feeds.

The current UI is the Astro frontend.

## Features

- FastAPI backend for feed management, analysis, crawling, and RSS output.
- Playwright crawler with Browserless Chrome support for JavaScript-rendered pages.
- MiniMax-powered structure analysis for list pages and article pages.
- PostgreSQL in Docker, with local host bind mount support.
- Astro + React Islands dashboard served by FastAPI in Docker.
- Optional debug output for crawler and AI analysis workflows.

## Repository Layout

```text
.
├── backend/                 # FastAPI API, crawler, AI analysis, RSS generation
├── frontend-astro/          # Primary Astro dashboard
├── tests/                   # Ad hoc/manual test scripts
├── Dockerfile               # App image: backend + built Astro frontend
├── docker-compose.yml       # App + PostgreSQL + Browserless Chrome
├── entrypoint.sh            # Container startup script
├── restart.sh               # Local non-Docker startup helper
├── .env.example             # Environment variable template
└── README.md
```

Ignored local-only directories:

- `data/`: PostgreSQL bind mount.
- `log/`: runtime logs, debug output, historical local outputs.
- `node_modules/`, `.venv/`, `venv/`, `.astro/`, `dist/`: generated dependencies/build output.
- `docs/` and non-README Markdown files are local AI development notes and are intentionally not published on `main`.

## Requirements

For Docker usage:

- Docker
- Docker Compose v2
- MiniMax API key

For local development without Docker:

- Python 3.11+
- Node.js 20+
- npm
- Playwright browser dependencies
- PostgreSQL

## Quick Start With Docker

Published app image:

```bash
docker pull jhangyu/palimpsest:0.01
```

1. Set the MiniMax API key in `docker-compose.yml` or in the Portainer stack editor:

```yaml
MINIMAX_API_KEY: "your_api_key_here"
```

2. Start the stack:

```bash
docker compose up --build
```

3. Open the services:

- App dashboard and Backend API: http://localhost:8088
- Browserless Chrome: http://localhost:3000

PostgreSQL data is mounted to:

```text
/Users/jhangyu/project/palimpsest/data/postgres
```

The app container also mounts the project data directory:

```text
/Users/jhangyu/project/palimpsest/data -> /app/data
```

This directory is intentionally ignored by Git.

The compose file uses explicit defaults instead of `${...}` interpolation and absolute host bind mounts so it can be imported directly into Portainer. If the project is moved, update the host-side paths in `docker-compose.yml`.

## Port Overrides

If local services already use the default ports, override them at startup:

```bash
# Edit docker-compose.yml:
# "8088:8088" -> "18088:8088"
# "3000:3000" -> "13000:3000"
docker compose up --build
```

Then open:

- App dashboard and Backend API: http://localhost:18088

## Local Development

The existing local startup helper starts the backend and Astro dev server:

```bash
./restart.sh
```

Expected local ports:

- Backend API: http://localhost:8088
- Astro frontend: http://localhost:5174

For manual backend startup:

```bash
cd backend
python -m uvicorn main:app --host 0.0.0.0 --port 8088
```

For manual Astro startup:

```bash
cd frontend-astro
npm install
npm run dev -- --host 0.0.0.0 --port 5174
```

## Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `MINIMAX_API_KEY` | empty | Required for AI selector analysis. |
| `POSTGRES_USER` | `palimpsest` | Docker PostgreSQL user. |
| `POSTGRES_PASSWORD` | `palimpsest` | Docker PostgreSQL password. |
| `POSTGRES_DB` | `palimpsest` | Docker PostgreSQL database. |
| `BACKEND_PORT` | `8088` | Host port for the Docker app and FastAPI. |
| `CHROME_PORT` | `3000` | Host port for Browserless Chrome. |
| `PALIMPSEST_LOG_DIR` | `/app/log` | Container log/debug artifact directory, bind-mounted from `./log`. |
| `MAX_CONCURRENT_SESSIONS` | `10` | Browserless Chrome concurrency limit. |
| `CHROME_CONNECTION_TIMEOUT` | `300000` | Browserless connection timeout in milliseconds. |

The backend also supports:

- `DATABASE_URL`
- `CHROME_MODE`
- `CHROME_WS_ENDPOINT`
- `BROWSER_WS_URL`

Docker Compose sets these automatically for the containerized stack.

## API Overview

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/analyze/list` | Analyze a list page and infer list selectors. |
| `POST` | `/analyze/content` | Analyze an article page and infer content selectors. |
| `POST` | `/crawl/preview` | Preview crawling without saving. |
| `GET` | `/sites/` | List configured sites. |
| `POST` | `/sites/` | Create a site and start crawling. |
| `GET` | `/sites/{id}` | Fetch one site. |
| `PUT` | `/sites/{id}` | Update one site. |
| `DELETE` | `/sites/{id}` | Delete one site and its articles. |
| `POST` | `/sites/{id}/duplicate` | Duplicate site settings. |
| `POST` | `/crawl/{id}` | Trigger a crawl for one site. |
| `GET` | `/rss/{identifier}` | Return the generated RSS feed. |

## Testing

Frontend Playwright tests live in `frontend-astro/tests/`.

Run them after starting the Astro dev server:

```bash
cd frontend-astro
npm install
npx playwright test
```

The `tests/` directory contains local/ad hoc verification scripts that are not part of the main CI path yet.

## Development Notes

- Keep AI development notes on the local-only `ai-notes` branch.
- Do not commit `.env`, `data/`, `log/`, local DB files, or dependency directories.
- Use Conventional Commits when committing changes.

## Security

Never commit real API keys or local database files. Use `.env.example` as the public template and keep `.env` private.

If an API key has ever been exposed in a shared log, screenshot, or commit, rotate it before publishing the repository.
