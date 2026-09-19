"""
数据库会话管理（由 pycore/integrations/db/session.py 模板扩展）。

SQLite 相对路径先解析为绝对路径并创建父目录；引擎按当前 ConfigManager 惰性创建。
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from pycore.core.config import get_config
from pycore.core.logger import get_logger

logger = get_logger()

BACKEND_DIR = Path(__file__).resolve().parents[2]

engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


def resolve_sqlite_path(database_path: str) -> Path:
    path = Path(database_path)
    if not path.is_absolute():
        path = (BACKEND_DIR / path).resolve()
    else:
        path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def build_database_url(database_path: str) -> str:
    return f"sqlite+aiosqlite:///{resolve_sqlite_path(database_path).as_posix()}"


def reset_engine() -> None:
    global engine, async_session_maker
    engine = None
    async_session_maker = None


def _ensure_engine() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    global engine, async_session_maker
    if engine is None or async_session_maker is None:
        settings = get_config().settings
        database_url = build_database_url(settings.database_path)
        engine = create_async_engine(database_url, echo=False, future=True)
        async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        logger.info("数据库引擎已创建", database_path=str(resolve_sqlite_path(settings.database_path)))
    return engine, async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（用于 FastAPI Depends）。"""
    _, session_maker = _ensure_engine()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """上下文管理器形式的数据库会话。"""
    _, session_maker = _ensure_engine()
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """初始化数据库（创建表）并在空表时写入内部账号种子。"""
    from src.db.models import Base
    from src.services.auth import AuthService

    current_engine, _ = _ensure_engine()
    async with current_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("数据库表已创建")

    async with get_db_context() as session:
        service = AuthService(session)
        created = await service.ensure_seed_user()
        if created:
            logger.info("内部账号种子已写入")
        else:
            logger.info("内部账号已存在，跳过种子")


async def close_db() -> None:
    """关闭数据库连接。"""
    global engine, async_session_maker
    if engine is not None:
        await engine.dispose()
        logger.info("数据库连接已关闭")
    engine = None
    async_session_maker = None
