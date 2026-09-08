"""Standalone analysis-job worker (PR-V2-05). Polls ``analysis_jobs`` using
``SELECT ... FOR UPDATE SKIP LOCKED`` -- the exact same pattern as `worker.py` (report
jobs), kept as a real separate module rather than generalizing `worker.py` itself:
the two poll different tables (`report_jobs` vs. `analysis_jobs`) with different row
shapes (a `ReportJob` maps 1:1 to a `Report`; an `AnalysisJob` maps 1:1 to either a
`RelationshipAnalysis` or a `ShadowDynamicsAnalysis`, selected by `analysis_type`) and
different service-layer run functions, so a generic shared poll loop would need a
dispatch layer that does not otherwise exist in this codebase -- MINIMAL TOUCH favors
this small, obviously-correct duplication over introducing that abstraction into
`worker.py` for a single new caller. Run as its own process
(``python -m numra_api.analysis_worker``); ``run_once=True`` lets tests drive a single
poll cycle deterministically.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from numra_api.config import get_settings
from numra_api.db import build_engine, build_sessionmaker
from numra_api.models.enums import AnalysisType
from numra_api.repositories.analysis import (
    claim_next_analysis_job,
    get_relationship_analysis_for_job,
    get_shadow_dynamics_analysis_for_job,
)
from numra_api.services.llm_factory import build_llm_provider
from numra_api.services.relationship_analysis_service import (
    run_relationship_analysis_job,
    run_shadow_dynamics_job,
)
from numra_interpretation.llm.types import LLMProvider

logger = logging.getLogger("numra_api.analysis_worker")

DEFAULT_LEASE_SECONDS = 300
DEFAULT_POLL_INTERVAL_SECONDS = 5


async def run_one_cycle(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    llm: LLMProvider,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> bool:
    """Claim and fully process at most one job. Returns True if a job was claimed,
    False if the queue was empty -- same contract as `worker.run_one_cycle`."""
    async with sessionmaker() as db:
        job = await claim_next_analysis_job(
            db, now=dt.datetime.now(dt.UTC), lease_seconds=lease_seconds
        )
        if job is None:
            await db.commit()
            return False

        if job.analysis_type == AnalysisType.RELATIONSHIP_INTERPRETATION:
            relationship_analysis = await get_relationship_analysis_for_job(db, job_id=job.id)
            if relationship_analysis is None:
                await db.commit()
                return True
            await run_relationship_analysis_job(
                db, job=job, analysis=relationship_analysis, llm=llm
            )
        else:
            shadow_analysis = await get_shadow_dynamics_analysis_for_job(db, job_id=job.id)
            if shadow_analysis is None:
                await db.commit()
                return True
            await run_shadow_dynamics_job(db, job=job, analysis=shadow_analysis, llm=llm)

        await db.commit()
        return True


async def run_forever(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    llm: LLMProvider,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> None:
    logger.info("NUMRA analysis worker starting (llm_provider=%s)", type(llm).__name__)
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
