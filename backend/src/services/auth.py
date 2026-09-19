"""内部账号鉴权：bcrypt + JWT，无服务端登出黑名单。"""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from pycore.core import get_logger
from src.config.settings import get_settings
from src.db.models import User
from src.models.auth import LoginData, UserPublic
from src.repositories.user import UserRepository

logger = get_logger()

JWT_ALGORITHM = "HS256"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


class AuthService:
    def __init__(self, db: AsyncSession):
        self.repo = UserRepository(db)

    def to_public(self, user: User) -> UserPublic:
        return UserPublic(id=user.id, username=user.username)

    async def ensure_seed_user(self) -> bool:
        if await self.repo.count() > 0:
            return False
        settings = get_settings()
        hashed = hash_password(settings.internal_password)
        await self.repo.create(settings.internal_username, hashed)
        return True

    async def authenticate(self, username: str, password: str) -> User | None:
        user = await self.repo.get_by_username(username)
        if user is None or not verify_password(password, user.hashed_password):
            logger.info("内部账号登录失败")
            return None
        logger.info("内部账号登录成功", user_id=user.id)
        return user

    def create_access_token(self, user: User) -> str:
        settings = get_settings()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "iat": now,
            "exp": now + timedelta(hours=settings.jwt_expire_hours),
        }
        return jwt.encode(payload, settings.secret_key, algorithm=JWT_ALGORITHM)

    def build_login_data(self, user: User) -> LoginData:
        return LoginData(
            access_token=self.create_access_token(user),
            token_type="bearer",
            user=self.to_public(user),
        )

    def decode_access_token(self, token: str) -> int | None:
        settings = get_settings()
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[JWT_ALGORITHM],
            )
        except jwt.PyJWTError:
            return None
        sub = payload.get("sub")
        if sub is None:
            return None
        try:
            return int(sub)
        except (TypeError, ValueError):
            return None

    async def get_user_by_id(self, user_id: int) -> User | None:
        return await self.repo.get_by_id(user_id)
