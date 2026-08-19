"""Standalone report-job worker. Polls ``report_jobs`` using ``SELECT ... FOR UPDATE
SKIP LOCKED`` so multiple worker processes can run concurrently without double-processing
a job (master prompt §110). Run as its own process/container in production
(``python -m numra_api.worker``); ``run_once=True`` lets tests drive a single poll cycle
deterministically instead of running an infinite loop.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from numra_api.config import get_settings
from numra_api.db import build_engine, build_sessionmaker
from numra_api.repositories.reports import claim_next_job, get_report_for_user
from numra_api.services.llm_factory import build_llm_provider
from numra_api.services.report_service import run_report_job
from numra_interpretation.llm.types import LLMProvider

logger = logging.getLogger("numra_api.worker")

DEFAULT_LEASE_SECONDS = 300
DEFAULT_POLL_INTERVAL_SECONDS = 5


async def run_one_cycle(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    llm: LLMProvider,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> bool:
    """Claim and fully process at most one job. Returns True if a job was claimed
    (whether it ultimately succeeded or failed), False if the queue was empty.

    ``llm`` is required and never defaulted here — the caller (`run_forever`/`_main`
    for the real worker process, or a test fixture) must decide explicitly which
    provider this cycle uses. See `numra_api.services.llm_factory.build_llm_provider`.
    """
    async with sessionmaker() as db:
        job = await claim_next_job(db, now=dt.datetime.now(dt.UTC), lease_seconds=lease_seconds)
        if job is None:
            await db.commit()
            return False

        report = await get_report_for_user(db, report_id=job.report_id, user_id=job.user_id)
        if report is None:
            await db.commit()
            return True

        await run_report_job(db, job=job, report=report, llm=llm)
        await db.commit()
        return True


async def run_forever(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    llm: LLMProvider,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> None:
    logger.info("NUMRA report worker starting (llm_provider=%s)", type(llm).__name__)
    while True:
        claimed = await run_one_cycle(sessionmaker, llm=llm, lease_seconds=lease_seconds)
        if not claimed:
            await asyncio.sleep(poll_interval_seconds)


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    engine = build_engine(settings.database_url)
    sessionmaker = build_sessionmaker(engine)
    llm = build_llm_provider(settings)
    try:
        await run_forever(sessionmaker, llm=llm)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
