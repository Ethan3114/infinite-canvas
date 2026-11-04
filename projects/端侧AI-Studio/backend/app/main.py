"""本地服务入口。页面和钥匙分开：钥匙只留在这个进程里。"""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.openai_gateway import router as openai_router
from app.api.routes import router
from app.core.config import Settings, load_settings
from app.models import Base
from app.services.providers import DeepSeekClient, SenseTimeClient
from app.services.runner import recover_lock

log = logging.getLogger("studio")


def create_app(settings: Settings | None = None, card_client=None, image_client=None) -> FastAPI:
    settings = settings or load_settings()
    data_dir = settings.resolved_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "files").mkdir(parents=True, exist_ok=True)
    engine = create_engine(settings.resolved_database_url(), connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)
    Base.metadata.create_all(engine)
    db = factory()
    try:
        recover_lock(db)
    finally:
        db.close()

    app = FastAPI(title="端侧 AI Studio")
    app.state.settings = settings
    app.state.factory = factory
    app.state.card_client = card_client or DeepSeekClient(settings)
    app.state.image_client = image_client or SenseTimeClient(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.include_router(openai_router)

    @app.exception_handler(RequestValidationError)
    async def invalid(_: Request, __: RequestValidationError):
        return JSONResponse(status_code=400, content={"error": {"code": "invalid", "message": "填写的内容不完整"}})

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception):
        log.exception("未处理的错误：%s", exc.__class__.__name__)
        return JSONResponse(status_code=500, content={"error": {"code": "internal", "message": "这次没有完成，请再试一次"}})

    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="ui")
    return app


app = create_app()
