from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.admin import router as admin_router
from app.config import get_settings
from app.db import Base, engine
from app.scheduler import shutdown_scheduler, start_scheduler
from app.webhook import router as webhook_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    logger.info("app started")
    try:
        yield
    finally:
        shutdown_scheduler()
        logger.info("app shutdown")


app = FastAPI(title="wa-bot-klinik", version="0.1.0", lifespan=lifespan)
app.include_router(webhook_router)
app.include_router(admin_router)


@app.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "ok": True,
        "model": s.openrouter_model,
        "timezone": s.timezone,
    }
