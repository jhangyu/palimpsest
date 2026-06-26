"""
---
name: routers_init
description: "Router sub-package — re-exports all FastAPI routers for the Palimpsest API"
type: package
target:
  layer: backend
  domain: routing
spec_doc: null
test_file: null
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
