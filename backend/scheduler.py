"""
scheduler.py — APScheduler factory and PostgreSQL advisory lock helpers.

Interface contract:
  - create_scheduler(database_url) -> AsyncIOScheduler
      Returns an AsyncIOScheduler with persistent SQLAlchemy job store when
      database_url is provided, or in-memory store otherwise.

  - async acquire_scheduler_lock(db) -> bool
      Attempts to acquire a cluster-wide PostgreSQL advisory lock so that only
      one worker runs scheduled jobs.  Returns True if the lock was acquired.
      db must be an AsyncSession or AsyncConnection (SQLAlchemy 2.0 async).

  - async release_scheduler_lock(db) -> None
      Releases the advisory lock previously acquired by this session.
      Safe to call even if the lock is not held (PostgreSQL will ignore it).
      Must use the same db instance that acquired the lock.

  - setup_jobs(scheduler, crawl_fn, cleanup_fn) -> None
      Registers the two standard interval jobs on *scheduler*.
      crawl_fn  — async callable, runs every 1 h with ±300 s jitter.
      cleanup_fn — async callable, runs every 24 h with ±3600 s jitter.

All dependencies are passed as parameters; this module does NOT import from
main.py.
"""

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

# Arbitrary but stable 64-bit integer used as the advisory lock key.
# All workers in the cluster must use the same value.
_SCHEDULER_LOCK_ID: int = 0x50414C5F5343484E  # "PAL_SCHN" in hex


def create_scheduler(database_url: str | None = None) -> AsyncIOScheduler:
    """Return an AsyncIOScheduler with optional persistent job store.

    Parameters
    ----------
    database_url : str | None
        Async database URL (e.g. ``postgresql+asyncpg://...``).  When provided,
        the ``+asyncpg`` driver suffix is stripped so that APScheduler's
        synchronous SQLAlchemy job store can connect.  When *None*, the
        scheduler uses the default in-memory job store.
    """
    jobstores = {}
    if database_url:
        # APScheduler's SQLAlchemyJobStore requires a synchronous URL.
        sync_url = database_url.replace("+asyncpg", "")
        jobstores["default"] = SQLAlchemyJobStore(
            url=sync_url,
            tablename="apscheduler_jobs",
        )

    job_defaults = {
        "coalesce": True,           # Collapse missed runs into one execution
        "max_instances": 1,         # Prevent concurrent execution of the same job
        "misfire_grace_time": 300,  # 5-minute grace period for misfired jobs
    }

    return AsyncIOScheduler(
        jobstores=jobstores,
        job_defaults=job_defaults,
    )


async def acquire_scheduler_lock(db) -> bool:
    """
    Try to acquire a PostgreSQL session-level advisory lock.

    Parameters
    ----------
    db : AsyncSession | AsyncConnection
        An active SQLAlchemy async connection or session.

    Returns
    -------
    bool
        True  — lock acquired; this worker should start the scheduler.
        False — another worker already holds the lock; skip starting scheduler.
    """
    result = await db.execute(
        text("SELECT pg_try_advisory_lock(:lock_id) AS acquired"),
        {"lock_id": _SCHEDULER_LOCK_ID},
    )
    row = result.mappings().first()
    return bool(row["acquired"]) if row is not None else False


async def release_scheduler_lock(db) -> None:
    """
    Release the PostgreSQL session-level advisory lock.

    Parameters
    ----------
    db : AsyncSession | AsyncConnection
        An active SQLAlchemy async connection or session (same one that
        acquired the lock).

    Notes
    -----
    pg_advisory_unlock returns FALSE if the lock was not held; that is
    silently ignored here.
    """
    await db.execute(
        text("SELECT pg_advisory_unlock(:lock_id)"),
        {"lock_id": _SCHEDULER_LOCK_ID},
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
    scheduler.add_job(
        crawl_fn, "interval", hours=1, jitter=300,
        id="scheduled_crawl", replace_existing=True,
    )
    scheduler.add_job(
        cleanup_fn, "interval", hours=24, jitter=3600,
        id="session_cleanup", replace_existing=True,
    )
