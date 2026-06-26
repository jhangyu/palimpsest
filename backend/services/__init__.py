"""
---
name: services_init
description: "Services sub-package — pure business-logic layer with no FastAPI dependencies"
type: package
target:
  layer: backend
  domain: services
spec_doc: null
test_file: null
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
