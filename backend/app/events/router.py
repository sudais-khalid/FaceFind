import random
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_db
from app.db.models import DriveFile, Event, FaceEmbedding, SearchResult, User, UserProbeEmbedding
from app.dependencies import require_organizer
from app.events.models import (
    DeleteEventResponse,
    EventDetailResponse,
    EventJoinResponse,
    ReindexResponse,
)
from app.search.faiss_index import FAISSIndexManager

router = APIRouter(prefix="/api/events", tags=["events"])
settings = get_settings()

EVENT_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_event_code() -> str:
    """Generate a readable 6-character event code without ambiguous symbols."""
    return "".join(random.SystemRandom().choices(EVENT_CODE_ALPHABET, k=6))


async def generate_unique_event_code(db: AsyncSession) -> str:
    """Generate a unique event code, retrying on collision."""
    for _ in range(10):
        code = generate_event_code()
        result = await db.execute(select(Event).where(Event.event_code == code))
        if result.scalars().first() is None:
            return code
    raise RuntimeError("Could not generate unique event code")


def _parse_event_id(event_id: str) -> UUID:
    try:
        return UUID(event_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid event id")


def _event_detail(event: Event) -> EventDetailResponse:
    return EventDetailResponse(
        event_id=event.event_id,
        organizer_id=event.organizer_id,
        title=event.title,
        event_code=event.event_code,
        drive_folder_id=event.drive_folder_id,
        status=event.status.value if hasattr(event.status, "value") else str(event.status),
        files_total=event.files_total,
        files_indexed=event.files_indexed,
        created_at=event.created_at.isoformat() if event.created_at else None,
        last_indexed_at=event.last_indexed_at.isoformat() if event.last_indexed_at else None,
    )


@router.get("/{event_id}")
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> EventDetailResponse:
    parsed_id = _parse_event_id(event_id)
    result = await db.execute(select(Event).where(Event.event_id == parsed_id))
    event = result.scalars().first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_detail(event)


@router.delete("/{event_id}")
async def delete_event(
    event_id: str,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
) -> DeleteEventResponse:
    parsed_id = _parse_event_id(event_id)
    result = await db.execute(select(Event).where(Event.event_id == parsed_id))
    event = result.scalars().first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.organizer_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    await db.execute(delete(SearchResult).where(SearchResult.event_id == parsed_id))
    await db.execute(delete(UserProbeEmbedding).where(UserProbeEmbedding.event_id == parsed_id))
    await db.execute(delete(FaceEmbedding).where(FaceEmbedding.event_id == parsed_id))
    await db.execute(delete(DriveFile).where(DriveFile.event_id == parsed_id))
    await db.delete(event)
    await db.commit()

    FAISSIndexManager(settings.faiss_index_dir).delete_index(str(parsed_id))
    return DeleteEventResponse(event_id=parsed_id, deleted=True)


@router.post("/{event_id}/reindex")
async def reindex_event(
    event_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
) -> ReindexResponse:
    parsed_id = _parse_event_id(event_id)
    result = await db.execute(select(Event).where(Event.event_id == parsed_id))
    event = result.scalars().first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.organizer_id != user.user_id:
        raise HTTPException(status_code=403, detail="Not allowed")

    queued = False
    if settings.app_env == "development":
        from app.workers.indexing_task import _index_drive_folder

        background_tasks.add_task(_index_drive_folder, str(parsed_id))
        queued = True
    else:
        try:
            from app.workers.indexing_task import index_drive_folder

            index_drive_folder.delay(str(parsed_id))
            queued = True
        except Exception:
            queued = False

    return ReindexResponse(event_id=parsed_id, queued=queued)


@router.get("/join/{event_code}")
async def join_event(
    event_code: str,
    db: AsyncSession = Depends(get_db),
) -> EventJoinResponse:
    result = await db.execute(
        select(Event, User)
        .join(User, Event.organizer_id == User.user_id)
        .where(Event.event_code == event_code.upper())
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event, organizer = row
    return EventJoinResponse(
        event_id=event.event_id,
        title=event.title,
        organizer_name=organizer.name,
        event_code=event.event_code,
        files_total=event.files_total,
        status=event.status.value if hasattr(event.status, "value") else str(event.status),
    )
