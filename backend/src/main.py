from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pycore.api import APIConfig, APIServer, ErrorHandlerMiddleware, error_response
from pycore.core import Logger, LoggerConfig, LogLevel, get_logger

from src.api.routes import auth_router, conversations_router, documents_router, tickets_router
from src.api.ws import ws_router
from src.config.settings import get_settings, load_app_config
from src.db.session import close_db, init_db
from src.services.ingest import fail_interrupted_ingests
from src.spa import mount_frontend

Logger.configure(
    LoggerConfig(
        level=LogLevel.INFO,
        app_name="customer-service",
        json_format=False,
        file_enabled=False,
    )
)
logger = get_logger()

load_app_config()
settings = get_settings()

server = APIServer(
    APIConfig(
        title="Customer Service API",
        version="0.1.0",
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
        cors_origins=list(settings.cors_origins),
    )
)

async def on_startup() -> None:
    await init_db()
    await fail_interrupted_ingests()


server.on_startup(on_startup)
server.on_shutdown(close_db)
server.include_router(auth_router)
server.include_router(documents_router)
server.include_router(conversations_router)
server.include_router(tickets_router)
server.include_router(ws_router)
server.add_middleware(ErrorHandlerMiddleware, debug=settings.debug)

ERROR_CODES = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
}


def _error_json(error: str, error_code: str, status_code: int) -> JSONResponse:
    resp, code = error_response(error=error, error_code=error_code, status_code=status_code)
    return JSONResponse(status_code=code, content=jsonable_encoder(resp))


@server.app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    del exc
    path = request.url.path.rstrip("/")
    message = "请输入用户名和密码" if path.endswith("/auth/login") else "参数验证失败"
    return _error_json(message, "VALIDATION_ERROR", 400)


@server.app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    del request
    detail = exc.detail if isinstance(exc.detail, str) else "请求失败"
    error_code = ERROR_CODES.get(exc.status_code, "INTERNAL_ERROR")
    return _error_json(detail, error_code, exc.status_code)


app = server.app
mount_frontend(app)
logger.info("应用已装配", host=settings.host, port=settings.port)
