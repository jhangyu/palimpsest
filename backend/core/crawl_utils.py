# backend/core/crawl_utils.py — 向後相容，所有實作已遷移到 parser.py
"""
---
name: crawl_utils
description: "Backward-compatibility shim: re-exports all symbols from core.parser; all implementations have been migrated to parser.py"
type: core
target:
  layer: backend
  domain: crawl
spec_doc: null
test_file: null
functions: []
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
from core.parser import *
