"""Versioned schema migrations."""
from .registry import Migration, MIGRATIONS, run_migrations

# Import migration modules to trigger self-registration into MIGRATIONS
from . import v001_initial  # noqa: F401
from . import v002_ai_providers  # noqa: F401
# v003_crawl_repair is NOT imported here — migrate_crawl_repair_tables()
# commits internally, which breaks the run_migrations transaction.
# It is called separately in main.py's _run_all_migrations.

__all__ = ["Migration", "MIGRATIONS", "run_migrations"]
