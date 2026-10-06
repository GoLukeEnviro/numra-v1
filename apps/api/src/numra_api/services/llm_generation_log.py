"""PII-sicheres Nutzungslog fuer LLM-Aufrufe (`llm_generations`), Phase 6b / F07a.

Geschrieben werden ausschliesslich Metadaten: Quelle, Provider/Modell, Status, Versuch,
Latenz, optionale Provider-Tokens und ein HMAC-SHA256 des gerenderten Prompts (Schluessel:
`Settings.session_secret`; ungesalzene Hashes ueber niedrig-entrope Nutzer-/Profiltexte
waeren per Woerterbuch umkehrbar. Der Hash dient nur dem Gleichheitsvergleich -- ein
Secret-Wechsel aendert ihn, das ist gewollt). Nie Prompt, Antwort oder Fehlertext
(Provider-Fehlermeldungen koennen Antwortinhalt enthalten, daher wird nur der
Exception-Klassenname als `error_code` gespeichert). Tokenzahlen werden nur gespeichert,
wenn der Provider sie liefert -- nie geschaetzt oder aus Text abgeleitet.

Best effort, nie auf Kosten des Nutzerpfads: `record` schreibt in einem SAVEPOINT der
Aufrufer-Transaktion (eine eigene Verbindung wuerde auf der vom Worker per
`FOR UPDATE` gesperrten `report_jobs`-Zeile blockieren, weil der FK-Insert ein
`FOR KEY SHARE` darauf nimmt) und faengt jeden Fehler beim Schreiben ab -- er wird
geloggt, die Aufrufer-Transaktion bleibt intakt. Folge der gemeinsamen Transaktion:
bricht der Job ab oder stirbt der Worker vor dem Commit, gehen die Zeilen dieses Laufs
verloren. Das ist bewusst so.

Dieselbe Strategie fuer alle drei Quellen: Analyse-Worker (Job-Transaktion mit
`FOR UPDATE` auf `analysis_jobs`) und Copilot (die Request-Transaktion, die auch die
ASSISTANT-Nachricht anlegt; synchron, kein Streaming) schreiben im SAVEPOINT der
Aufrufer-Session, nie ueber eine eigene Verbindung (FK-Insert nimmt `FOR KEY SHARE` auf
die Elternzeile). Beim Copilot ist die Elternzeile die eigene, noch nicht committete
ASSISTANT-Nachricht; ein Log-Fehler kippt weder Antwort noch FAILED-Persistierung.

`attempt` ist der Job-Versuch. Die Pipeline wiederholt einen Abschnitt bei verworfener
Ausgabe einmal innerhalb desselben Job-Versuchs (Reparatur); diese Aufrufe tragen daher
dieselbe `attempt`-Nummer (unterscheidbar ueber `section_id` und `created_at`).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Literal, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.config import get_settings
from numra_api.models import LLMGeneration
from numra_api.repositories.reports import MAX_ATTEMPTS
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
_UNHASHABLE = "0" * 64


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
    analysis_job_id: uuid.UUID | None = None,
    chat_message_id: uuid.UUID | None = None,
    section_id: str | None = None,
    error_code: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
) -> bool:
    """Schreibt eine Zeile; True bei Erfolg, False (geloggt) bei jedem Schreibfehler.

    Ausstehende Aenderungen des Aufrufers werden vorab ausserhalb des Fangnetzes
    geflusht: ein Fehler darin ist der des Aufrufers und wird nicht verschluckt."""
    await db.flush()
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
                    analysis_job_id=analysis_job_id,
                    chat_message_id=chat_message_id,
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
    key = get_settings().session_secret.encode("utf-8")
    return hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def _safe_prompt_hash(request: GenerationRequest) -> str:
    """Ein Hash-Fehler darf weder Provider-Ergebnis noch -Exception ueberdecken."""
    try:
        return _prompt_hash(request)
    except Exception:  # noqa: BLE001
        logger.exception("llm_generations: Prompt-Hash nicht berechenbar")
        return _UNHASHABLE


class RecordingLLMProvider:
    """Decorator um einen `LLMProvider`: protokolliert jeden `generate*`-Aufruf eines
    Pfads (Report-Worker, Analyse-Worker, Copilot) als eine `llm_generations`-Zeile und
    reicht Ergebnis bzw. Exception unveraendert durch. `health` wird nicht protokolliert
    (kein Generierungsaufruf).

    Genau eine Herkunft je Instanz: `job_id` (Report), `analysis_job_id` (Analyse) oder
    `chat_message_id` (Copilot-ASSISTANT-Nachricht), passend zu `source`.

    Status: `ok`; `retry` nur bei einem retrybaren `LLMProviderError` UND wenn der Aufrufer
    noch einen weiteren Versuch hat (`attempt < max_attempts`, wie
    `report_service._handle_job_failure`); sonst `error`. Der Copilot hat keine
    Job-Wiederholung (der Nutzer sendet neu) und uebergibt `max_attempts=1` -- dort gibt es
    nie `retry`."""

    def __init__(
        self,
        inner: LLMProvider,
        db: AsyncSession,
        *,
        attempt: int,
        source: GenerationSource = "report",
        job_id: uuid.UUID | None = None,
        analysis_job_id: uuid.UUID | None = None,
        chat_message_id: uuid.UUID | None = None,
        max_attempts: int = MAX_ATTEMPTS,
    ):
        self._inner = inner
        self._db = db
        self._source: GenerationSource = source
        self._job_id = job_id
        self._analysis_job_id = analysis_job_id
        self._chat_message_id = chat_message_id
        self._attempt = attempt
        self._max_attempts = max_attempts

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
        prompt_hash = _safe_prompt_hash(request)
        started = time.perf_counter()
        status: GenerationStatus = "ok"
        error_code: str | None = None
        try:
            return await call()
        except Exception as exc:
            will_retry = (
                isinstance(exc, LLMProviderError)
                and exc.retryable
                and self._attempt < self._max_attempts
            )
            status = "retry" if will_retry else "error"
            error_code = type(exc).__name__
            raise
        finally:
            await record(
                self._db,
                source=self._source,
                provider=getattr(self._inner, "provider_name", type(self._inner).__name__),
                model=getattr(self._inner, model_attr, "unknown"),
                status=status,
                attempt=self._attempt,
                prompt_hash=prompt_hash,
                latency_ms=round((time.perf_counter() - started) * 1000),
                report_job_id=self._job_id,
                analysis_job_id=self._analysis_job_id,
                chat_message_id=self._chat_message_id,
                section_id=request.metadata.get("section_id"),
                error_code=error_code,
            )
