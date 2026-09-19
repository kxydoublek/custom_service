"""生产环境把 frontend/dist 挂到同一端口，浏览器同源访问 /api 与 /ws。"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pycore.core import get_logger
from starlette.staticfiles import StaticFiles

from src.config.settings import BACKEND_DIR

logger = get_logger()

FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"
_RESERVED_EXACT = {"api", "ws", "health", "docs", "redoc", "openapi.json"}


def _is_reserved(full_path: str) -> bool:
    return full_path in _RESERVED_EXACT or full_path.startswith("api/")


def mount_frontend(app: FastAPI) -> None:
    index = FRONTEND_DIST / "index.html"
    if not index.is_file():
        logger.info("未找到前端构建产物，仅提供 API")
        return

    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    dist_root = FRONTEND_DIST.resolve()

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        if _is_reserved(full_path):
            raise HTTPException(status_code=404, detail="未找到")
        target = (FRONTEND_DIST / full_path).resolve()
        try:
            target.relative_to(dist_root)
        except ValueError:
            return FileResponse(index)
        if full_path and target.is_file():
            return FileResponse(target)
        return FileResponse(index)

    logger.info("已挂载前端静态页", dist=str(FRONTEND_DIST))
