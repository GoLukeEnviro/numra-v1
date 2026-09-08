from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.auth.csrf import CSRF_COOKIE_NAME
from numra_api.auth.passwords import verify_password
from numra_api.deps import get_current_user, get_db, get_export_storage, require_csrf
from numra_api.models import User
from numra_api.schemas.account import DeleteAccountRequest
from numra_api.services.account_deletion_service import delete_own_account
from numra_api.services.errors import InvalidCredentials
from numra_api.storage.exports import ExportStorage

router = APIRouter(prefix="/v1/account", tags=["account"])


@router.post("/delete-all", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_all_route(
    body: DeleteAccountRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ExportStorage = Depends(get_export_storage),
) -> None:
    if not verify_password(user.password_hash, body.password):
        raise InvalidCredentials("password confirmation did not match")
    await delete_own_account(db, user=user, storage=storage)
    response.delete_cookie("numra_session", path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
