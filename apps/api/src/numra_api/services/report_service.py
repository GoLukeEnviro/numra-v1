from __future__ import annotations

import datetime as dt
import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.config import Settings
from numra_api.models import Calculation, Report, ReportJob
from numra_api.models.enums import BetaFeature, ContentFlag, ReportJobStatus, ReportType
from numra_api.repositories.calculations import get_calculation_for_user
from numra_api.repositories.reports import (
    MAX_ATTEMPTS,
    create_report_with_job,
    fail_job_terminally,
    fail_report,
    finalize_report,
    get_live_regeneration,
    get_report_for_user,
    get_report_job_by_idempotency_key,
    mark_job_status,
    persist_report_sections,
    requeue_job_for_retry,
)
from numra_api.services.content_flag import report_flags
from numra_api.services.errors import ContentNotFlagged, IdempotencyKeyConflict, NotFoundError
from numra_api.services.llm_generation_log import RecordingLLMProvider
from numra_api.services.persistence_gate import assert_no_unresolved_tokens
from numra_api.services.regeneration import RegenerationPreview
from numra_api.services.usage_quota import reserve, snapshot
from numra_interpretation.errors import InvalidReportSection
from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_interpretation.llm.errors import LLMProviderError
from numra_interpretation.llm.types import LLMProvider
from numra_interpretation.report import build_manifest, generate_report
from numra_interpretation.report.pipeline import ReportGenerationError
from numra_numerology.models.profile import CanonicalProfile

logger = logging.getLogger("numra_api.report_service")

REPO_ROOT = Path(__file__).resolve().parents[5]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"
REPORT_SCHEMA_VERSION = "1.0.0"
#: Kept in sync with `numra_interpretation.report.manifest.ReportManifest`'s own
#: `prompt_version` default — see that field's docstring (V1.6 C timing-report fix).
PROMPT_VERSION = "numra-report-v2"


async def create_report_job(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    calculation_id: uuid.UUID,
    report_type: ReportType,
    idempotency_key: str | None,
    settings: Settings,
) -> tuple[Report, ReportJob]:
    if idempotency_key is not None:
        existing_job = await get_report_job_by_idempotency_key(
            db, user_id=user_id, idempotency_key=idempotency_key
        )
        if existing_job is not None:
            report = await get_report_for_user(
                db, report_id=existing_job.report_id, user_id=user_id
            )
            assert report is not None
            return report, existing_job

    calculation = await get_calculation_for_user(db, calculation_id=calculation_id, user_id=user_id)
    if calculation is None:
        raise NotFoundError(f"calculation {calculation_id} not found")
    return await _enqueue_report(
        db,
        user_id=user_id,
        calculation=calculation,
        report_type=report_type,
        idempotency_key=idempotency_key,
        settings=settings,
        regenerated_from_id=None,
    )


async def _enqueue_report(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    calculation: Calculation,
    report_type: ReportType,
    idempotency_key: str | None,
    settings: Settings,
    regenerated_from_id: uuid.UUID | None,
) -> tuple[Report, ReportJob]:
    """The part of a start that fresh generations and regenerations share: a PENDING
    report with its QUEUED job and one reserved unit of quota."""
    # Read the knowledge package's own declared version rather than hardcoding it --
    # a stale literal here would silently mislabel every report once the knowledge
    # package is re-versioned (V1.5 Epic J).
    knowledge_version = load_knowledge_base(KNOWLEDGE_ROOT).manifest.version

    report, job = await create_report_with_job(
        db,
        user_id=user_id,
        calculation_id=calculation.id,
        report_type=report_type,
        calculation_version=calculation.calculation_version,
        knowledge_version=knowledge_version,
        prompt_version=PROMPT_VERSION,
        profile_snapshot=calculation.canonical_profile_json,
        report_schema_version=REPORT_SCHEMA_VERSION,
        idempotency_key=idempotency_key,
        regenerated_from_id=regenerated_from_id,
    )
    # After the idempotency early-return above: a retry with the same key never gets here.
    await reserve(db, settings=settings, user_id=user_id, feature=BetaFeature.REPORT, ref_id=job.id)
    return report, job


async def preview_report_regeneration(
    db: AsyncSession, *, user_id: uuid.UUID, report_id: uuid.UUID, settings: Settings
) -> RegenerationPreview:
    """Read-only: what regenerating this report would do. Only the owner sees it."""
    original = await get_report_for_user(db, report_id=report_id, user_id=user_id)
    if original is None:
        raise NotFoundError(f"report {report_id} not found")
    successor = await get_live_regeneration(db, report_id=original.id)
    return RegenerationPreview(
        content_flag=report_flags(original).content_flag,
        feature=BetaFeature.REPORT,
        existing_regeneration_id=None if successor is None else successor.id,
        quota=await snapshot(db, settings=settings, user_id=user_id, feature=BetaFeature.REPORT),
    )


async def regenerate_report_job(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    report_id: uuid.UUID,
    idempotency_key: str | None,
    settings: Settings,
) -> tuple[Report, ReportJob, bool]:
    """Start a NEW report linked to a flagged one (``regenerated_from_id``); the original
    is never changed. Returns ``(report, job, created)``; ``created`` is False when the
    call only returned something that already exists (same Idempotency-Key, or a live
    regeneration of this original) -- so a double click yields one version, one quota
    unit and one LLM call. The original row is locked for the duration of the check, which
    serialises concurrent clicks; the partial unique index backs that up in the database.
    """
    original = await get_report_for_user(db, report_id=report_id, user_id=user_id, for_update=True)
    if original is None:
        raise NotFoundError(f"report {report_id} not found")

    if idempotency_key is not None:
        existing_job = await get_report_job_by_idempotency_key(
            db, user_id=user_id, idempotency_key=idempotency_key
        )
        if existing_job is not None:
            replayed = await get_report_for_user(
                db, report_id=existing_job.report_id, user_id=user_id
            )
            if replayed is None or replayed.regenerated_from_id != original.id:
                raise IdempotencyKeyConflict("Idempotency-Key belongs to a different request")
            return replayed, existing_job, False

    successor = await get_live_regeneration(db, report_id=original.id)
    if successor is not None:
        return successor, successor.jobs[0], False

    if report_flags(original).content_flag is ContentFlag.NONE:
        raise ContentNotFlagged(f"report {report_id} has no unresolved template tokens")

    calculation = await get_calculation_for_user(
        db, calculation_id=original.calculation_id, user_id=user_id
    )
    if calculation is None:
        raise NotFoundError(f"calculation {original.calculation_id} not found")
    report, job = await _enqueue_report(
        db,
        user_id=user_id,
        calculation=calculation,
        report_type=ReportType(original.report_type),
        idempotency_key=idempotency_key,
        settings=settings,
        regenerated_from_id=original.id,
    )
    return report, job, True


async def _handle_job_failure(
    db: AsyncSession, *, job: ReportJob, report: Report, error_code: str, retryable: bool
) -> None:
    """Route a failed attempt to either a backoff-scheduled retry (job goes back to
    QUEUED, a reclaimable status) or a terminal FAILED, depending on whether the
    failure is retryable and whether attempts remain. Only a terminal FAILED also fails
    the parent `Report` — a job still awaiting retry leaves the report PENDING, since
    the job may yet succeed."""
    now = dt.datetime.now(dt.UTC)
    if retryable and job.attempt_count < MAX_ATTEMPTS:
        await requeue_job_for_retry(db, job=job, now=now, error_code=error_code)
    else:
        await fail_job_terminally(db, job=job, now=now, error_code=error_code)
        await fail_report(db, report=report)


async def run_report_job(
    db: AsyncSession, *, job: ReportJob, report: Report, llm: LLMProvider
) -> None:
    """Execute one report job end-to-end: OUTLINE -> GENERATING -> VALIDATING ->
    ASSEMBLING -> COMPLETE/FAILED (or back to QUEUED for a backoff-scheduled retry).
    Assumes the caller already claimed ``job`` (i.e. ``claim_next_job`` was used, so
    this call is exclusive to one worker).

    ``llm`` must be an explicit provider chosen by the caller (see
    ``numra_api.services.llm_factory.build_llm_provider``) — this function never
    silently substitutes a mock. Every exception path below is caught and routed to
    `_handle_job_failure`: a raw provider/network exception must never propagate out of
    here and crash the worker loop (see `numra_api.worker.run_one_cycle`)."""
    llm = RecordingLLMProvider(llm, db, job_id=job.id, attempt=job.attempt_count)
    try:
        await mark_job_status(db, job=job, status=ReportJobStatus.GENERATING, progress=10)

        profile = CanonicalProfile.model_validate(report.profile_snapshot)
        knowledge = load_knowledge_base(KNOWLEDGE_ROOT)
        # SQLAlchemy stores this as a plain VARCHAR (no Enum column type bound), so a
        # freshly-constructed-then-flushed ORM object may still hold the ReportType
        # enum member while a reloaded one holds a plain str — normalize either way.
        report_type_value = (
            report.report_type.value
            if isinstance(report.report_type, ReportType)
            else str(report.report_type)
        )
        manifest = build_manifest(
            report_type=report_type_value,  # type: ignore[arg-type]
            calculation_id=str(report.calculation_id),
        )

        structured_report = await generate_report(
            profile=profile, knowledge=knowledge, manifest=manifest, llm=llm
        )

        await mark_job_status(db, job=job, status=ReportJobStatus.VALIDATING, progress=70)
        await mark_job_status(db, job=job, status=ReportJobStatus.ASSEMBLING, progress=85)

        sections_payload = [
            {
                "section_id": section.section_id,
                "title": section.title,
                "order_index": section.order_index,
                "text": section.text,
                "word_count": section.word_count,
                "summary": section.summary,
                "metric_refs": list(section.metric_refs),
                "knowledge_refs": list(section.knowledge_refs),
            }
            for section in structured_report.sections
        ]
        content_json = {
            "report_type": structured_report.report_type,
            "language": structured_report.language,
            "calculation_version": structured_report.calculation_version,
            "knowledge_version": structured_report.knowledge_version,
            "prompt_version": structured_report.prompt_version,
            "model_provider": structured_report.model_provider,
            "model_name": structured_report.model_name,
            "total_word_count": structured_report.total_word_count,
            "sections": sections_payload,
        }
        assert_no_unresolved_tokens(
            content_json,
            strict_braces=False,
            error=ReportGenerationError,
            code="REPORT_VALIDATION_FAILED",
        )
        await persist_report_sections(db, report=report, sections=sections_payload)
        await finalize_report(
            db, report=report, content_json=content_json, generated_at=dt.datetime.now(dt.UTC)
        )
        await mark_job_status(db, job=job, status=ReportJobStatus.COMPLETE, progress=100)

    except ReportGenerationError as exc:
        # Pipeline-level failures (LLM unavailable, lint/schema validation failed) are
        # treated as retryable: a fresh generation attempt — possibly once transient
        # provider trouble clears — may succeed where this one didn't.
        #
        # Der gespeicherte Fehlercode bleibt eine reine Kategorie: er wird dem Nutzer im
        # Fortschritts-DOM woertlich angezeigt (`report-progress-view.tsx`). Interne
        # Details (Section-Ids, Lint-Regelnamen, Klassen-Reprs) gehoeren ins Log, nicht
        # in die Oberflaeche (#137).
        logger.warning("Report job %s failed during generation: %s", job.id, exc)
        await _handle_job_failure(
            db,
            job=job,
            report=report,
            error_code="REPORT_GENERATION_ERROR",
            retryable=True,
        )
    except InvalidReportSection as exc:
        # Verteidigungslinie: die Pipeline normalisiert Abschnittsfehler nach zwei
        # Versuchen selbst zu `ReportGenerationError` (#137). Kaeme der Typ trotzdem
        # hier an, gehoert er in dieselbe Klasse — validiert, retrybar — und darf nicht
        # als UNEXPECTED_ERROR ohne Retry enden.
        logger.warning("Report job %s rejected a section: %s", job.id, exc)
        await _handle_job_failure(
            db,
            job=job,
            report=report,
            error_code="REPORT_VALIDATION_FAILED",
            retryable=True,
        )
    except LLMProviderError as exc:
        # Any provider failure the pipeline didn't already normalize into a
        # ReportGenerationError (e.g. a timeout/5xx raised mid-section-generation).
        # `exc.retryable` — set by the provider's own error classification — decides
        # backoff-and-retry vs. terminal failure.
        logger.warning("Report job %s failed at the provider: %s", job.id, exc)
        await _handle_job_failure(
            db,
            job=job,
            report=report,
            error_code="LLM_PROVIDER_ERROR",
            retryable=exc.retryable,
        )
    except Exception:  # noqa: BLE001 - last-resort guard, see docstring above
        # An unexpected bug (not a known provider/pipeline failure type) must still
        # never crash the worker's poll loop. Treated as non-retryable: an
        # unclassified failure is not known to be transient, so retrying blind could
        # spin through all attempts on a bug that will never succeed.
        logger.exception("Unexpected error while running report job %s", job.id)
        await _handle_job_failure(
            db, job=job, report=report, error_code="UNEXPECTED_ERROR", retryable=False
        )
