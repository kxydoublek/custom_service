from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(User))
        return int(result.scalar_one())

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def create(self, username: str, hashed_password: str) -> User:
        user = User(username=username, hashed_password=hashed_password)
        self.db.add(user)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ValueError("数据冲突: 用户名已存在") from exc
        await self.db.refresh(user)
        return user
