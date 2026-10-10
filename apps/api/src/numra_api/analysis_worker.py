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
from numra_api.models import AnalysisJob
from numra_api.models.enums import AnalysisType, BetaFeature
from numra_api.repositories.analysis import (
    claim_next_analysis_job,
    fail_job_terminally,
    fail_relationship_analysis,
    fail_shadow_dynamics_analysis,
    get_relationship_analysis_for_job,
    get_shadow_dynamics_analysis_for_job,
)
from numra_api.repositories.entitlements import user_has_beta_feature
from numra_api.services.llm_factory import build_llm_provider
from numra_api.services.relationship_analysis_service import (
    run_relationship_analysis_job,
    run_shadow_dynamics_job,
)
from numra_interpretation.llm.types import LLMProvider

logger = logging.getLogger("numra_api.analysis_worker")

DEFAULT_LEASE_SECONDS = 300
DEFAULT_POLL_INTERVAL_SECONDS = 5


async def _fail_for_missing_beta_access(db: AsyncSession, *, job: AnalysisJob) -> None:
    await fail_job_terminally(
        db, job=job, now=dt.datetime.now(dt.UTC), error_code="BETA_ACCESS_REQUIRED"
    )
    if job.analysis_type == AnalysisType.RELATIONSHIP_INTERPRETATION:
        analysis = await get_relationship_analysis_for_job(db, job_id=job.id)
        if analysis is not None:
            await fail_relationship_analysis(db, analysis=analysis)
    else:
        shadow = await get_shadow_dynamics_analysis_for_job(db, job_id=job.id)
        if shadow is not None:
            await fail_shadow_dynamics_analysis(db, analysis=shadow)


async def run_one_cycle(
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    llm: LLMProvider,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    beta_gate_enforced: bool = False,
) -> bool:
    """Claim and fully process at most one job. Returns True if a job was claimed,
    False if the queue was empty -- same contract as `worker.run_one_cycle`
    (including the ``beta_gate_enforced`` start check)."""
    async with sessionmaker() as db:
        job = await claim_next_analysis_job(
            db, now=dt.datetime.now(dt.UTC), lease_seconds=lease_seconds
        )
        if job is None:
            await db.commit()
            return False

        if beta_gate_enforced and not await user_has_beta_feature(
            db, user_id=job.requested_by_user_id, feature=BetaFeature.ANALYSIS
        ):
            await _fail_for_missing_beta_access(db, job=job)
            await db.commit()
            return True

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
    beta_gate_enforced: bool = False,
) -> None:
    logger.info("NUMRA analysis worker starting (llm_provider=%s)", type(llm).__name__)
    while True:
        claimed = await run_one_cycle(
            sessionmaker,
            llm=llm,
            lease_seconds=lease_seconds,
            beta_gate_enforced=beta_gate_enforced,
        )
        if not claimed:
            await asyncio.sleep(poll_interval_seconds)


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    engine = build_engine(settings.database_url)
    sessionmaker = build_sessionmaker(engine)
    llm = build_llm_provider(settings)
    try:
        await run_forever(sessionmaker, llm=llm, beta_gate_enforced=settings.beta_gate_enforced)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
