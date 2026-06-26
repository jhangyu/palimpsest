# backend/core/crypto.py
"""
---
name: crypto
description: "AES-GCM encryption helpers placeholder — vault functions removed in #24; all user_ai_tokens encryption was deprecated"
type: core
target:
  layer: backend
  domain: auth
spec_doc: null
test_file: tests/stage1/test_kek_lifecycle.py
functions: []
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
