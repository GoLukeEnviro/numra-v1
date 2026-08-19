from __future__ import annotations

from enum import StrEnum


class ReportType(StrEnum):
    QUICK = "QUICK"
    FULL = "FULL"
    ULTIMATE = "ULTIMATE"
    CUSTOM = "CUSTOM"


class ReportJobStatus(StrEnum):
    QUEUED = "QUEUED"
    OUTLINE = "OUTLINE"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    ASSEMBLING = "ASSEMBLING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NameIdentityKind(StrEnum):
    BIRTH = "birth"
    CURRENT = "current"
    PREFERRED = "preferred"


class ExportType(StrEnum):
    PDF = "pdf"
    JSON = "json"


class ExportStatus(StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"
