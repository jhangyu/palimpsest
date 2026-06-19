"""Unified logging utilities module.

Provides a single source of truth for common logging patterns across the application.
"""

from datetime import datetime


def log_with_time(msg: str) -> None:
    """Log a message with a timestamp prefix.

    Args:
        msg: The message to log.
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")
