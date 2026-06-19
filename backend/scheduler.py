"""
scheduler.py — APScheduler factory and PostgreSQL advisory lock helpers.

Interface contract:
  - create_scheduler() -> AsyncIOScheduler
      Returns a fresh, unconfigured AsyncIOScheduler instance.

  - async acquire_scheduler_lock(db) -> bool
      Attempts to acquire a cluster-wide PostgreSQL advisory lock so that only
      one worker runs scheduled jobs.  Returns True if the lock was acquired.
      db must be a databases.Database instance.

  - async release_scheduler_lock(db) -> None
      Releases the advisory lock previously acquired by this session.
      Safe to call even if the lock is not held (PostgreSQL will ignore it).

  - setup_jobs(scheduler, crawl_fn, cleanup_fn) -> None
      Registers the two standard interval jobs on *scheduler*.
      crawl_fn  — async callable, runs every 1 h with ±300 s jitter.
      cleanup_fn — async callable, runs every 24 h with ±3600 s jitter.

All dependencies are passed as parameters; this module does NOT import from
main.py.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Arbitrary but stable 64-bit integer used as the advisory lock key.
# All workers in the cluster must use the same value.
_SCHEDULER_LOCK_ID: int = 0x50414C5F5343484E  # "PAL_SCHN" in hex


def create_scheduler() -> AsyncIOScheduler:
    """Return a new AsyncIOScheduler ready to be configured and started."""
    return AsyncIOScheduler()


async def acquire_scheduler_lock(db) -> bool:
    """
    Try to acquire a PostgreSQL session-level advisory lock.

    Parameters
    ----------
    db : databases.Database
        An active databases.Database connection.

    Returns
    -------
    bool
        True  — lock acquired; this worker should start the scheduler.
        False — another worker already holds the lock; skip starting scheduler.
    """
    row = await db.fetch_one(
        "SELECT pg_try_advisory_lock(:lock_id) AS acquired",
        values={"lock_id": _SCHEDULER_LOCK_ID},
    )
    return bool(row["acquired"]) if row is not None else False


async def release_scheduler_lock(db) -> None:
    """
    Release the PostgreSQL session-level advisory lock.

    Parameters
    ----------
    db : databases.Database
        An active databases.Database connection (same session that acquired
        the lock).

    Notes
    -----
    pg_advisory_unlock returns FALSE if the lock was not held; that is
    silently ignored here.
    """
    await db.execute(
        "SELECT pg_advisory_unlock(:lock_id)",
        values={"lock_id": _SCHEDULER_LOCK_ID},
    )


def setup_jobs(scheduler: AsyncIOScheduler, crawl_fn, cleanup_fn) -> None:
    """
    Register the standard interval jobs on *scheduler*.

    Parameters
    ----------
    scheduler : AsyncIOScheduler
        A scheduler instance returned by create_scheduler() (not yet started).
    crawl_fn : async callable
        Job that crawls all due sites; runs every 1 hour ± 300 s jitter.
    cleanup_fn : async callable
        Job that purges expired sessions/tokens; runs every 24 hours ± 3600 s.
    """
    scheduler.add_job(crawl_fn, "interval", hours=1, jitter=300)
    scheduler.add_job(cleanup_fn, "interval", hours=24, jitter=3600)
