"""PR-V2-05 -- relationship-analysis / shadow-dynamics job creation + execution.

Mirrors `services/report_service.py`'s job-creation/run-job split: `create_*_job`
validates preconditions and enqueues a job synchronously (callable without a worker
running -- tests exercise generation directly via `run_*_job`), `run_*_job` is what
`analysis_worker.py` calls once it has claimed a job.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import AnalysisJob, Calculation, RelationshipAnalysis, ShadowDynamicsAnalysis
from numra_api.models.enums import (
    AnalysisJobStatus,
    AnalysisType,
    ConsentScope,
    WorkspaceMemberStatus,
)
from numra_api.repositories.analysis import (
    MAX_ATTEMPTS,
    create_analysis_job,
    create_pending_relationship_analysis,
    create_pending_shadow_dynamics_analysis,
    fail_job_terminally,
    fail_relationship_analysis,
    fail_shadow_dynamics_analysis,
    finalize_relationship_analysis,
    finalize_shadow_dynamics_analysis,
    get_analysis_job_by_idempotency_key,
    get_relationship_analysis_for_job,
    get_shadow_dynamics_analysis_for_job,
    mark_job_status,
    requeue_job_for_retry,
)
from numra_api.repositories.calculations import get_latest_calculation_for_person
from numra_api.repositories.workspaces import (
    get_self_person_for_member,
    get_workspace_by_id,
    get_workspace_member,
    list_workspace_members,
)
from numra_api.services.consent_service import assert_consent
from numra_api.services.errors import (
    KnowledgeFrameNotAvailable,
    NotFoundError,
    RelationshipTypeNotSet,
    SelfProfileRequired,
)
from numra_api.services.workspace_guard import assert_workspace_active
from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_interpretation.llm.errors import LLMProviderError
from numra_interpretation.llm.types import LLMProvider
from numra_numerology.models.profile import CanonicalProfile
from numra_relationship_interpretation.errors import (
    AnalysisGenerationError,
    ShadowInteractionRuleMissing,
)
from numra_relationship_interpretation.knowledge_loader import (
    load_relationship_frame,
    load_relationship_frames_manifest,
    load_shadow_interaction_manifest,
    load_shadow_interaction_rules,
)
from numra_relationship_interpretation.pipeline import (
    PROMPT_VERSION,
    generate_relationship_analysis,
    generate_shadow_dynamics,
)

logger = logging.getLogger("numra_api.relationship_analysis_service")

REPO_ROOT = Path(__file__).resolve().parents[5]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"


class _WorkspacePreconditions:
    def __init__(
        self,
        *,
        relationship_type: str,
        member_a_user_id: uuid.UUID,
        member_b_user_id: uuid.UUID,
        person_a_id: uuid.UUID,
        person_b_id: uuid.UUID,
    ) -> None:
        self.relationship_type = relationship_type
        self.member_a_user_id = member_a_user_id
        self.member_b_user_id = member_b_user_id
        self.person_a_id = person_a_id
        self.person_b_id = person_b_id


async def _check_workspace_preconditions(
    db: AsyncSession, *, workspace_id: uuid.UUID, requester_user_id: uuid.UUID
) -> _WorkspacePreconditions:
    """Steps 1-4 of the blueprint's `create_*_job` preconditions, shared by both
    relationship-analysis and shadow-dynamics job creation."""
    workspace = await get_workspace_by_id(db, workspace_id=workspace_id)
    if workspace is None:
        raise NotFoundError(f"workspace {workspace_id} not found")

    requester_member = await get_workspace_member(
        db, workspace_id=workspace_id, user_id=requester_user_id
    )
    if requester_member is None:
        # IDOR: requester is not an ACTIVE member of this workspace -- 404, not 403
        # (never confirm the workspace exists to a non-member).
        raise NotFoundError(f"workspace {workspace_id} not found")

    # PR-V2-10 -- immer NACH dem IDOR-Gate, nie davor (siehe
    # services/workspace_guard.py docstring): kein neuer Analysis-Job für einen
    # DISSOLVED Workspace, weder Relationship-Interpretation noch Shadow-Dynamics.
    await assert_workspace_active(db, workspace=workspace)

    if workspace.relationship_type is None:
        raise RelationshipTypeNotSet(f"workspace {workspace_id} has no relationship_type set")

    members = await list_workspace_members(db, workspace_id=workspace_id)
    active_members = [m.user_id for m in members if m.status == WorkspaceMemberStatus.ACTIVE]
    if len(active_members) != 2:
        raise NotFoundError(f"workspace {workspace_id} has no counterpart member")
    user_a_id, user_b_id = active_members[0], active_members[1]

    person_a = await get_self_person_for_member(db, user_id=user_a_id)
    person_b = await get_self_person_for_member(db, user_id=user_b_id)
    if person_a is None or person_b is None:
        raise SelfProfileRequired(
            "both workspace members must have a SELF-mode Person profile before "
            "relationship/shadow-dynamics analysis can run"
        )

    return _WorkspacePreconditions(
        relationship_type=workspace.relationship_type,
        member_a_user_id=user_a_id,
        member_b_user_id=user_b_id,
        person_a_id=person_a.id,
        person_b_id=person_b.id,
    )


async def _assert_mutual_relationship_consent(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_a_id: uuid.UUID, user_b_id: uuid.UUID
) -> None:
    """Both directions must have an active RELATIONSHIP_INSIGHTS grant -- a shared
    two-person analysis needs consent from both sides, not just the requester's own
    grant (specs/v2/shadow-dynamics-spec.md "Consent gating")."""
    await assert_consent(
        db,
        workspace_id=workspace_id,
        grantor_user_id=user_a_id,
        grantee_user_id=user_b_id,
        scope=ConsentScope.RELATIONSHIP_INSIGHTS.value,
    )
    await assert_consent(
        db,
        workspace_id=workspace_id,
        grantor_user_id=user_b_id,
        grantee_user_id=user_a_id,
        scope=ConsentScope.RELATIONSHIP_INSIGHTS.value,
    )


async def create_relationship_analysis_job(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    requester_user_id: uuid.UUID,
    idempotency_key: str | None,
) -> tuple[AnalysisJob, RelationshipAnalysis]:
    if idempotency_key is not None:
        existing = await get_analysis_job_by_idempotency_key(
            db, user_id=requester_user_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            analysis = await get_relationship_analysis_for_job(db, job_id=existing.id)
            assert analysis is not None
            return existing, analysis

    preconditions = await _check_workspace_preconditions(
        db, workspace_id=workspace_id, requester_user_id=requester_user_id
    )

    frame = load_relationship_frame(KNOWLEDGE_ROOT, preconditions.relationship_type)
    if frame is None:
        raise KnowledgeFrameNotAvailable(
            f"no relationship-frame knowledge for relationship_type="
            f"{preconditions.relationship_type!r}"
        )

    await _assert_mutual_relationship_consent(
        db,
        workspace_id=workspace_id,
        user_a_id=preconditions.member_a_user_id,
        user_b_id=preconditions.member_b_user_id,
    )

    calculation_a = await get_latest_calculation_for_person(
        db, person_id=preconditions.person_a_id, user_id=preconditions.member_a_user_id
    )
    calculation_b = await get_latest_calculation_for_person(
        db, person_id=preconditions.person_b_id, user_id=preconditions.member_b_user_id
    )
    if calculation_a is None or calculation_b is None:
        raise SelfProfileRequired(
            "both workspace members must have at least one Calculation before "
            "relationship analysis can run"
        )

    knowledge_version = load_relationship_frames_manifest(KNOWLEDGE_ROOT).version

    job = await create_analysis_job(
        db,
        workspace_id=workspace_id,
        requested_by_user_id=requester_user_id,
        analysis_type=AnalysisType.RELATIONSHIP_INTERPRETATION,
        idempotency_key=idempotency_key,
    )
    analysis = await create_pending_relationship_analysis(
        db,
        workspace_id=workspace_id,
        job_id=job.id,
        relationship_type=preconditions.relationship_type,
        calculation_a_id=calculation_a.id,
        calculation_b_id=calculation_b.id,
        calculation_version=calculation_a.calculation_version,
        knowledge_version=knowledge_version,
        prompt_version=PROMPT_VERSION,
    )
    return job, analysis


async def create_shadow_dynamics_job(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    requester_user_id: uuid.UUID,
    idempotency_key: str | None,
) -> tuple[AnalysisJob, ShadowDynamicsAnalysis]:
    if idempotency_key is not None:
        existing = await get_analysis_job_by_idempotency_key(
            db, user_id=requester_user_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            analysis = await get_shadow_dynamics_analysis_for_job(db, job_id=existing.id)
            assert analysis is not None
            return existing, analysis

    # Shadow Dynamics is type-agnostic (works from knowledge/shadow-interaction/rules.yaml,
    # not a relationship-frame file) -- step 3 of the blueprint ("nur relevant für
    # Relationship-Interpretation") is deliberately skipped here.
    preconditions = await _check_workspace_preconditions(
        db, workspace_id=workspace_id, requester_user_id=requester_user_id
    )

    await _assert_mutual_relationship_consent(
        db,
        workspace_id=workspace_id,
        user_a_id=preconditions.member_a_user_id,
        user_b_id=preconditions.member_b_user_id,
    )

    calculation_a = await get_latest_calculation_for_person(
        db, person_id=preconditions.person_a_id, user_id=preconditions.member_a_user_id
    )
    calculation_b = await get_latest_calculation_for_person(
        db, person_id=preconditions.person_b_id, user_id=preconditions.member_b_user_id
    )
    if calculation_a is None or calculation_b is None:
        raise SelfProfileRequired(
            "both workspace members must have at least one Calculation before "
            "shadow-dynamics analysis can run"
        )

    knowledge_version = load_shadow_interaction_manifest(KNOWLEDGE_ROOT).version

    job = await create_analysis_job(
        db,
        workspace_id=workspace_id,
        requested_by_user_id=requester_user_id,
        analysis_type=AnalysisType.SHADOW_DYNAMICS,
        idempotency_key=idempotency_key,
    )
    analysis = await create_pending_shadow_dynamics_analysis(
        db,
        workspace_id=workspace_id,
        job_id=job.id,
        relationship_type=preconditions.relationship_type,
        calculation_a_id=calculation_a.id,
        calculation_b_id=calculation_b.id,
        calculation_version=calculation_a.calculation_version,
        knowledge_version=knowledge_version,
        prompt_version=PROMPT_VERSION,
    )
    return job, analysis


async def _handle_job_failure(
    db: AsyncSession,
    *,
    job: AnalysisJob,
    fail_analysis: Any,
    error_code: str,
    retryable: bool,
) -> None:
    """Same retry-vs-terminal routing as `report_service._handle_job_failure`."""
    now = dt.datetime.now(dt.UTC)
    if retryable and job.attempt_count < MAX_ATTEMPTS:
        await requeue_job_for_retry(db, job=job, now=now, error_code=error_code)
    else:
        await fail_job_terminally(db, job=job, now=now, error_code=error_code)
        await fail_analysis()


async def run_relationship_analysis_job(
    db: AsyncSession, *, job: AnalysisJob, analysis: RelationshipAnalysis, llm: LLMProvider
) -> None:
    """Execute one relationship-analysis job end-to-end (assumes the caller already
    claimed ``job`` via `claim_next_analysis_job`)."""
    await mark_job_status(db, job=job, status=AnalysisJobStatus.GENERATING, progress=10)

    # `calculation_a_id`/`calculation_b_id` are snapshotted onto `analysis` at job
    # creation time -- reloading them is kept outside the try/except below on
    # purpose: a missing Calculation row here is a data-integrity bug, not a
    # pipeline failure the retry/backoff machinery should swallow.
    calc_a = await db.get(Calculation, analysis.calculation_a_id)
    calc_b = await db.get(Calculation, analysis.calculation_b_id)
    assert calc_a is not None and calc_b is not None

    try:
        profile_a = CanonicalProfile.model_validate(calc_a.canonical_profile_json)
        profile_b = CanonicalProfile.model_validate(calc_b.canonical_profile_json)

        frame = load_relationship_frame(KNOWLEDGE_ROOT, analysis.relationship_type)
        if frame is None:
            raise AnalysisGenerationError(
                f"KNOWLEDGE_FRAME_NOT_AVAILABLE: {analysis.relationship_type!r}"
            )

        result = await generate_relationship_analysis(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type=analysis.relationship_type,
            frame_knowledge=frame,
            llm=llm,
            knowledge_version=analysis.knowledge_version,
        )

        await mark_job_status(db, job=job, status=AnalysisJobStatus.VALIDATING, progress=80)

        result_json = result.model_dump(mode="json")
        await finalize_relationship_analysis(
            db,
            analysis=analysis,
            result_json=result_json,
            model_provider=result.model_provider,
            model_name=result.model_name,
            generated_at=dt.datetime.now(dt.UTC),
        )
        await mark_job_status(db, job=job, status=AnalysisJobStatus.COMPLETE, progress=100)

    except AnalysisGenerationError as exc:
        await _handle_job_failure(
            db,
            job=job,
            fail_analysis=lambda: fail_relationship_analysis(db, analysis=analysis),
            error_code=f"ANALYSIS_GENERATION_ERROR: {exc}",
            retryable=True,
        )
    except LLMProviderError as exc:
        await _handle_job_failure(
            db,
            job=job,
            fail_analysis=lambda: fail_relationship_analysis(db, analysis=analysis),
            error_code=f"LLM_PROVIDER_ERROR: {exc}",
            retryable=exc.retryable,
        )
    except Exception as exc:  # noqa: BLE001 - last-resort guard, see report_service.py
        logger.exception("Unexpected error while running relationship analysis job %s", job.id)
        await _handle_job_failure(
            db,
            job=job,
            fail_analysis=lambda: fail_relationship_analysis(db, analysis=analysis),
            error_code=f"UNEXPECTED_ERROR: {exc}",
            retryable=False,
        )


async def run_shadow_dynamics_job(
    db: AsyncSession, *, job: AnalysisJob, analysis: ShadowDynamicsAnalysis, llm: LLMProvider
) -> None:
    """Execute one shadow-dynamics job end-to-end -- same structure as
    `run_relationship_analysis_job`."""
    await mark_job_status(db, job=job, status=AnalysisJobStatus.GENERATING, progress=10)

    calc_a = await db.get(Calculation, analysis.calculation_a_id)
    calc_b = await db.get(Calculation, analysis.calculation_b_id)
    assert calc_a is not None and calc_b is not None

    try:
        profile_a = CanonicalProfile.model_validate(calc_a.canonical_profile_json)
        profile_b = CanonicalProfile.model_validate(calc_b.canonical_profile_json)

        knowledge = load_knowledge_base(KNOWLEDGE_ROOT)
        shadow_rules = load_shadow_interaction_rules(KNOWLEDGE_ROOT)

        result = await generate_shadow_dynamics(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type=analysis.relationship_type,
            knowledge=knowledge,
            shadow_rules=shadow_rules,
            llm=llm,
            knowledge_version=analysis.knowledge_version,
        )

        await mark_job_status(db, job=job, status=AnalysisJobStatus.VALIDATING, progress=80)

        result_json = result.model_dump(mode="json")
        await finalize_shadow_dynamics_analysis(
            db,
            analysis=analysis,
            result_json=result_json,
            model_provider=result.model_provider,
            model_name=result.model_name,
            generated_at=dt.datetime.now(dt.UTC),
        )
        await mark_job_status(db, job=job, status=AnalysisJobStatus.COMPLETE, progress=100)

    except ShadowInteractionRuleMissing as exc:
        # Permanent knowledge-content gap (no rules.yaml row for this shadow-theme
        # pair) -- a retry would resolve the same missing row. Terminal, not retryable.
        logger.warning("shadow interaction rule missing for job %s: %s", job.id, exc)
        await _handle_job_failure(
            db,
            job=job,
            fail_analysis=lambda: fail_shadow_dynamics_analysis(db, analysis=analysis),
            error_code=f"ANALYSIS_GENERATION_ERROR: {exc}",
            retryable=False,
        )
    except AnalysisGenerationError as exc:
        await _handle_job_failure(
            db,
            job=job,
            fail_analysis=lambda: fail_shadow_dynamics_analysis(db, analysis=analysis),
            error_code=f"ANALYSIS_GENERATION_ERROR: {exc}",
            retryable=True,
        )
    except LLMProviderError as exc:
        await _handle_job_failure(
            db,
            job=job,
            fail_analysis=lambda: fail_shadow_dynamics_analysis(db, analysis=analysis),
            error_code=f"LLM_PROVIDER_ERROR: {exc}",
            retryable=exc.retryable,
        )
    except Exception as exc:  # noqa: BLE001 - last-resort guard, see report_service.py
        logger.exception("Unexpected error while running shadow dynamics job %s", job.id)
        await _handle_job_failure(
            db,
            job=job,
            fail_analysis=lambda: fail_shadow_dynamics_analysis(db, analysis=analysis),
            error_code=f"UNEXPECTED_ERROR: {exc}",
            retryable=False,
        )
