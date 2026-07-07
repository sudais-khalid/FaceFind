import os
from pathlib import Path
import subprocess
from sqlalchemy import text
from app.db.database import Base, engine
from app.db import models  # noqa: F401 - registers ORM models on Base.metadata
from app.config import get_settings


async def init_db() -> None:
    """Initialize database with migrations"""
    # Run Alembic when available. In local development we also create any
    # missing tables from metadata so a failed migration command cannot leave
    # the API running against an empty database.
    env = os.environ.copy()
    project_root = Path(__file__).resolve().parents[3]
    env["PYTHONPATH"] = str(project_root / "backend")
    database_url = get_settings().database_url
    env["DATABASE_URL"] = database_url

    if "+asyncpg" not in database_url:
        result = subprocess.run(
            ["alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            print(f"Migration failed, falling back to metadata create_all: {result.stderr}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_db_connection() -> bool:
    """Check if database connection is working"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
