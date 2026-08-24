from __future__ import annotations

import datetime as dt
import logging
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import Report, ReportJob
from numra_api.models.enums import ReportJobStatus, ReportType
from numra_api.repositories.calculations import get_calculation_for_user
from numra_api.repositories.reports import (
    MAX_ATTEMPTS,
    create_report_with_job,
    fail_job_terminally,
    fail_report,
    finalize_report,
    get_report_for_user,
    get_report_job_by_idempotency_key,
    mark_job_status,
    persist_report_sections,
    requeue_job_for_retry,
)
from numra_api.services.errors import NotFoundError
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
PROMPT_VERSION = "numra-report-v3"
