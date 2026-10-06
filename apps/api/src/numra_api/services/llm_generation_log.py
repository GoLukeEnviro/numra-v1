"""PII-sicheres Nutzungslog fuer LLM-Aufrufe (`llm_generations`), Phase 6b / F07a.

Geschrieben werden ausschliesslich Metadaten: Quelle, Provider/Modell, Status, Versuch,
Latenz, optionale Provider-Tokens und ein SHA-256 des gerenderten Prompts. Nie Prompt,
Antwort oder Fehlertext (Provider-Fehlermeldungen koennen Antwortinhalt enthalten, daher
wird nur der Exception-Klassenname als `error_code` gespeichert). Tokenzahlen werden nur
gespeichert, wenn der Provider sie liefert -- nie geschaetzt oder aus Text abgeleitet.

Das Log darf den Nutzerpfad nie scheitern lassen: `record` schreibt in einem SAVEPOINT der
Aufrufer-Transaktion (eine eigene Verbindung wuerde auf der vom Worker per
`FOR UPDATE` gesperrten `report_jobs`-Zeile blockieren, weil der FK-Insert ein
`FOR KEY SHARE` darauf nimmt) und faengt jeden Fehler ab -- er wird geloggt, die
Aufrufer-Transaktion bleibt intakt.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import LLMGeneration
from numra_interpretation.llm.errors import LLMProviderError
from numra_interpretation.llm.types import (
    GenerationRequest,
    GenerationResult,
    LLMProvider,
    ProviderHealth,
    StructuredGenerationRequest,
)

__all__ = ["GenerationSource", "GenerationStatus", "RecordingLLMProvider", "record"]

logger = logging.getLogger("numra_api.llm_generation_log")

GenerationSource = Literal["report", "analysis", "copilot"]
GenerationStatus = Literal["ok", "error", "retry"]
_T = TypeVar("_T")


async def record(
    db: AsyncSession,
    *,
    source: GenerationSource,
    provider: str,
    model: str,
    status: GenerationStatus,
    attempt: int,
    prompt_hash: str,
    latency_ms: int | None = None,
    report_job_id: uuid.UUID | None = None,
    section_id: str | None = None,
    error_code: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
) -> bool:
    """Schreibt eine Zeile; True bei Erfolg, False (geloggt) bei jedem Fehler."""
    try:
        async with db.begin_nested():
            db.add(
                LLMGeneration(
                    source=source,
                    provider=provider,
                    model=model,
                    status=status,
                    attempt=attempt,
                    prompt_hash=prompt_hash,
                    latency_ms=latency_ms,
                    report_job_id=report_job_id,
                    section_id=section_id,
                    error_code=error_code,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
            )
        return True
    except Exception:  # noqa: BLE001 - das Log darf den Nutzerpfad nie scheitern lassen
        logger.exception("llm_generations: Zeile nicht geschrieben (source=%s)", source)
        return False


def _prompt_hash(request: GenerationRequest) -> str:
    payload = request.model_dump(mode="json", exclude={"metadata"})
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RecordingLLMProvider:
    """Decorator um einen `LLMProvider`: protokolliert jeden `generate*`-Aufruf des
    Report-Pfads als eine `llm_generations`-Zeile und reicht Ergebnis bzw. Exception
    unveraendert durch. `health` wird nicht protokolliert (kein Generierungsaufruf)."""

    def __init__(self, inner: LLMProvider, db: AsyncSession, *, job_id: uuid.UUID, attempt: int):
        self._inner = inner
        self._db = db
        self._job_id = job_id
        self._attempt = attempt

    async def health(self) -> ProviderHealth:
        return await self._inner.health()

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        return await self._logged(request, "fast_model", lambda: self._inner.generate(request))

    async def generate_structured(
        self, request: StructuredGenerationRequest, schema: type[BaseModel]
    ) -> BaseModel:
        return await self._logged(
            request, "premium_model", lambda: self._inner.generate_structured(request, schema)
        )

    async def _logged(
        self, request: GenerationRequest, model_attr: str, call: Callable[[], Awaitable[_T]]
    ) -> _T:
        started = time.perf_counter()
        status: GenerationStatus = "ok"
        error_code: str | None = None
        try:
            return await call()
        except Exception as exc:
            retryable = isinstance(exc, LLMProviderError) and exc.retryable
            status = "retry" if retryable else "error"
            error_code = type(exc).__name__
            raise
        finally:
            await record(
                self._db,
                source="report",
                provider=getattr(self._inner, "provider_name", type(self._inner).__name__),
                model=getattr(self._inner, model_attr, "unknown"),
                status=status,
                attempt=self._attempt,
                prompt_hash=_prompt_hash(request),
                latency_ms=round((time.perf_counter() - started) * 1000),
                report_job_id=self._job_id,
                section_id=request.metadata.get("section_id"),
                error_code=error_code,
            )
