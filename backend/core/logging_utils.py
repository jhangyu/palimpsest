"""
---
name: logging_utils
description: "Unified logging utilities: single source of truth for timestamped log output across the application"
type: core
target:
  layer: backend
  domain: auth
spec_doc: null
test_file: null
functions:
  - name: log_with_time
    line: 9
    purpose: "Print message prefixed with current datetime timestamp"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

from datetime import datetime


def log_with_time(msg: str) -> None:
    """Log a message with a timestamp prefix.

    Args:
        msg: The message to log.
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
