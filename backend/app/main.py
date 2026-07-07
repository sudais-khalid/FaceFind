from contextlib import asynccontextmanager
from pathlib import Path

import redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import get_settings
from app.db.database import engine
from app.db.init_db import check_db_connection, init_db
from app.drive.router import router as drive_router
from app.events.router import router as events_router
from app.search.router import get_cv_pipeline, get_index_manager, router as search_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.faiss_index_dir).mkdir(parents=True, exist_ok=True)
    app.state.redis = redis.from_url(settings.redis_url)
    app.state.cv_pipeline = get_cv_pipeline()
    app.state.faiss_index_manager = get_index_manager()
    try:
        if settings.app_env != "test":
            await init_db()
    except Exception as exc:
        app.state.startup_error = str(exc)
    yield
    await engine.dispose()
    try:
        app.state.redis.close()
    except Exception:
        pass


app = FastAPI(title="FaceFind", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(events_router)
app.include_router(drive_router)
app.include_router(search_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/detailed")
async def detailed_health() -> dict:
    db_ok = await check_db_connection()
    redis_ok = False
    try:
        redis_ok = bool(app.state.redis.ping())
    except Exception:
        redis_ok = False

    index_manager = get_index_manager()
    return {
        "status": "ok" if db_ok and redis_ok else "degraded",
        "version": "1.0.0",
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "faiss_loaded_indexes": len(index_manager.indexes),
        "cv_pipeline": "loaded" if getattr(app.state, "cv_pipeline", None) else "not_loaded",
        "startup_error": getattr(app.state, "startup_error", None),
    }
