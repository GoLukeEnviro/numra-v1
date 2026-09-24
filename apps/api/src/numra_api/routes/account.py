from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.auth.csrf import CSRF_COOKIE_NAME
from numra_api.auth.passwords import verify_password
from numra_api.config import Settings
from numra_api.deps import (
    get_current_user,
    get_db,
    get_export_storage,
    get_settings_dep,
    rate_limit_by_user,
    require_csrf,
)
from numra_api.models import User
from numra_api.schemas.account import DeleteAccountRequest
from numra_api.services.account_deletion_service import delete_own_account
from numra_api.services.account_export_service import export_filename, iter_account_export
from numra_api.services.errors import InvalidCredentials
from numra_api.storage.exports import ExportStorage

router = APIRouter(prefix="/v1/account", tags=["account"])


@router.get(
    "/export",
    dependencies=[
        Depends(rate_limit_by_user("account:export", limit=10, window_seconds=3600)),
    ],
)
async def export_account_route(
    request: Request,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Der eigene, strukturierte Kontodatenexport (PWA-07, #125).

    `StreamingResponse`, weil das Dokument Kategorie fuer Kategorie erzeugt wird: der
    Speicherbedarf haengt an der groessten Einzelkategorie statt an der Kontogroesse
    (siehe `services/account_export_service.py`).

    Die Session holt der Generator sich selbst aus dem `sessionmaker` -- bewusst
    *nicht* ueber `Depends(get_db, scope="function")`: FastAPI schliesst
    funktionsgebundene Dependencies vor dem Streaming des Bodys, eine dort geliehene
    Session waere also schon zu, bevor die erste Kategorie geschrieben ist (Details im
    Modul-Docstring des Services).

    Bewusst ein reines `GET`: die Anfrage veraendert nichts, und der Browser soll den
    Download direkt ausloesen koennen. Es gibt deshalb auch keine CSRF-Pruefung --
    dieselbe Begruendung wie bei `GET /v1/exports`.
    """
    generated_at = dt.datetime.now(dt.UTC)
    return StreamingResponse(
        iter_account_export(request.app.state.sessionmaker, user=user, now=generated_at),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{export_filename(generated_at)}"',
            # Ein Kontodatenexport gehoert in keinen Zwischenspeicher -- weder in den
            # des Browsers noch in den eines Proxys.
            "Cache-Control": "no-store",
        },
    )


@router.post("/delete-all", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_all_route(
    body: DeleteAccountRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
    storage: ExportStorage = Depends(get_export_storage),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    if not verify_password(user.password_hash, body.password):
        raise InvalidCredentials("password confirmation did not match")
    await delete_own_account(db, user=user, storage=storage)
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
