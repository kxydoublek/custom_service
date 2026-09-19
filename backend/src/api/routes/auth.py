from fastapi import Depends, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pycore.api import APIRouter, error_response, success_response
from pycore.api.routes import handle_errors
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user
from src.db.models import User
from src.db.session import get_db
from src.models.auth import LoginRequest, LogoutData, UserPublic
from src.services.auth import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
@handle_errors
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    user = await service.authenticate(body.username, body.password)
    if user is None:
        resp, code = error_response(
            error="账号或密码不正确",
            error_code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
        return JSONResponse(status_code=code, content=jsonable_encoder(resp))
    return success_response(data=service.build_login_data(user).model_dump(), message="ok")


@router.get("/me")
@handle_errors
async def me(user: User = Depends(get_current_user)):
    return success_response(
        data=UserPublic(id=user.id, username=user.username).model_dump(),
        message="ok",
    )


@router.post("/logout")
@handle_errors
async def logout():
    return success_response(data=LogoutData(logged_out=True).model_dump(), message="ok")
