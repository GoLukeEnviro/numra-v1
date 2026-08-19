from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.auth.csrf import CSRF_COOKIE_NAME
from numra_api.auth.passwords import verify_password
from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import User
from numra_api.repositories.account import delete_all_user_data
from numra_api.schemas.account import DeleteAccountRequest
from numra_api.services.errors import InvalidCredentials

router = APIRouter(prefix="/v1/account", tags=["account"])


@router.post("/delete-all", status_code=204, dependencies=[Depends(require_csrf)])
async def delete_all_route(
    body: DeleteAccountRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not verify_password(user.password_hash, body.password):
        raise InvalidCredentials("password confirmation did not match")
    await delete_all_user_data(db, user_id=user.id)
    response.delete_cookie("numra_session", path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
