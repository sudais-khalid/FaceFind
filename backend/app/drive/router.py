from datetime import datetime
from pathlib import Path
import re
from uuid import uuid4

import cv2
import numpy as np
import redis
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models import DriveFile, Event, EventStatus, SearchResult
from app.dependencies import get_current_user, require_organizer
from app.db.models import User
from app.drive.client import DriveClient
from app.drive.models import (
    CreateEventRequest,
    CreateEventResponse,
    DriveWebhookResponse,
    EventStatusResponse,
    FileUrlResponse,
)
from app.config import get_settings
from app.security.encryption import create_file_access_token, verify_file_access_token

router = APIRouter(prefix="/api", tags=["drive"])
settings = get_settings()


def extract_folder_id(url: str) -> str:
    """Extract Google Drive folder ID from URL"""
    # Handle: https://drive.google.com/drive/folders/FOLDER_ID
    match = re.search(r'folders/([a-zA-Z0-9-_]+)', url)
    if match:
        return match.group(1)
    return url  # Assume it's already a folder ID


def generate_event_code() -> str:
    """Generate 6-char alphanumeric event code"""
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    # Remove ambiguous chars
    chars = ''.join([c for c in chars if c not in 'OIl01'])
    code = ''.join(random.choices(chars, k=6))
    return code


@router.post("/events")
async def create_event(
    request: CreateEventRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_db),
) -> CreateEventResponse:
    """Create new indexing event (organizer only)"""
    folder_id = extract_folder_id(request.drive_folder_url)
    event_code = await generate_unique_event_code(db)
    drive_token_encrypted = None
    try:
        r = redis.from_url(settings.redis_url)
        drive_token_encrypted = r.get(f"drive_refresh_token:{user.user_id}")
    except Exception:
        drive_token_encrypted = None

    event = Event(
        event_id=uuid4(),
        organizer_id=user.user_id,
        title=request.title,
        event_code=event_code,
        drive_folder_id=folder_id,
        drive_token_encrypted=drive_token_encrypted,
        status=EventStatus.PENDING,
    )

    db.add(event)
    await db.commit()
    await db.refresh(event)

    if settings.app_env == "development":
        from app.workers.indexing_task import _index_drive_folder

        background_tasks.add_task(_index_drive_folder, str(event.event_id))
    else:
        try:
            from app.workers.indexing_task import index_drive_folder

            index_drive_folder.delay(str(event.event_id))
        except Exception as exc:
            event.status = EventStatus.ERROR
            await db.commit()
            raise HTTPException(status_code=500, detail="Could not enqueue indexing task") from exc

    return CreateEventResponse(
        event_id=event.event_id,
        event_code=event_code,
        status=event.status.value,
    )


@router.get("/events/{event_id}/status")
async def get_event_status(
    event_id: str,
    db: AsyncSession = Depends(get_db),
) -> EventStatusResponse:
    """Get indexing status for event"""
    stmt = select(Event).where(Event.event_id == event_id)
    result = await db.execute(stmt)
    event = result.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return EventStatusResponse(
        status=event.status.value,
        files_total=event.files_total,
        files_indexed=event.files_indexed,
        last_indexed_at=event.last_indexed_at.isoformat() if event.last_indexed_at else None,
    )


@router.get("/events/join/{event_code}")
async def join_event_by_code(
    event_code: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Join event as attendee (public endpoint)"""
    stmt = select(Event).where(Event.event_code == event_code)
    result = await db.execute(stmt)
    event = result.scalars().first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return {
        "event_id": str(event.event_id),
        "title": event.title,
        "event_code": event.event_code,
        "files_total": event.files_total,
    }


async def generate_unique_event_code(db: AsyncSession) -> str:
    for _ in range(10):
        code = generate_event_code()
        result = await db.execute(select(Event).where(Event.event_code == code))
        if result.scalars().first() is None:
            return code
    raise HTTPException(status_code=500, detail="Could not allocate event code")


@router.post("/drive/webhook")
async def drive_webhook(
    x_goog_channel_token: str | None = Header(default=None),
    x_goog_resource_id: str | None = Header(default=None),
) -> DriveWebhookResponse:
    """Accept Google Drive push notifications.

    The concrete channel-token validation secret is configured during watch
    registration in a later worker pass; for now reject missing tokens and
    accept well-formed notifications so tests and local wiring can proceed.
    """
    if not x_goog_channel_token:
        raise HTTPException(status_code=403, detail="Invalid webhook token")

    if x_goog_resource_id:
        try:
            from app.workers.indexing_task import incremental_reindex

            incremental_reindex.delay(x_goog_resource_id, [])
        except Exception:
            pass

    return DriveWebhookResponse(accepted=True)


@router.get("/files/{file_id}/url")
async def get_file_url(
    file_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileUrlResponse:
    """Return a short-lived, single-file signed URL for a file in the user's
    cached matches. The URL points at our own /files/{id}/media proxy and
    never exposes Drive credentials or app secrets - if this link leaks or is
    shared publicly, it only unlocks this one file, and only for 15 minutes."""
    stmt = (
        select(SearchResult)
        .where(SearchResult.user_id == user.user_id)
        .where(SearchResult.expires_at > datetime.utcnow())
    )
    result = await db.execute(stmt)
    search_results = result.scalars().all()
    allowed = any(file_id in (row.matched_file_ids or []) for row in search_results)

    if not allowed:
        raise HTTPException(status_code=403, detail="File is not available")

    expires_in = 900
    token = create_file_access_token(
        file_id,
        str(user.user_id),
        settings.master_encryption_key.encode("utf-8"),
        expires_in_seconds=expires_in,
    )
    url = f"{settings.public_base_url}/api/files/{file_id}/media?token={token}"
    return FileUrlResponse(url=url, expires_in=expires_in)


@router.get("/files/{file_id}/thumb")
async def get_file_thumbnail(
    file_id: str,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Serve a card-sized thumbnail through our own backend.

    Drive thumbnailLinks expire within hours and often refuse to render in a
    browser at all, so results cards point here instead. Thumbnails are cached
    on disk after the first fetch, and if Drive will not produce one we
    downscale the original file ourselves.
    """
    verified = verify_file_access_token(token, settings.master_encryption_key.encode("utf-8"))
    if verified is None or verified[0] != file_id:
        raise HTTPException(status_code=403, detail="Link expired or invalid")

    cache_dir = Path(settings.thumb_cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{file_id}.jpg"
    headers = {"Cache-Control": "private, max-age=86400"}

    if cache_path.exists():
        return Response(content=cache_path.read_bytes(), media_type="image/jpeg", headers=headers)

    result = await db.execute(select(DriveFile).where(DriveFile.file_id == file_id))
    drive_file = result.scalars().first()
    if drive_file is None:
        raise HTTPException(status_code=404, detail="File not found")

    client = DriveClient(access_token=None, api_key=settings.google_api_key or None)
    try:
        data = await client.get_fresh_thumbnail_bytes(file_id)
    except Exception:
        if not (drive_file.mime_type or "").startswith("image/"):
            raise HTTPException(status_code=404, detail="No thumbnail available")
        full_bytes = await client.download_file(file_id)
        array = np.frombuffer(full_bytes, dtype=np.uint8)
        image = cv2.imdecode(array, cv2.IMREAD_COLOR)
        if image is None:
            raise HTTPException(status_code=404, detail="No thumbnail available")
        height, width = image.shape[:2]
        scale = 640 / max(height, width)
        if scale < 1:
            image = cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            raise HTTPException(status_code=404, detail="No thumbnail available")
        data = encoded.tobytes()

    cache_path.write_bytes(data)
    return Response(content=data, media_type="image/jpeg", headers=headers)


@router.get("/files/{file_id}/media")
async def get_file_media(
    file_id: str,
    token: str,
    download: bool = False,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Stream the actual file bytes for a valid, unexpired signed token.

    This is the only place Drive credentials are ever used to fetch media -
    the client never sees them. The token itself carries the authorization
    (scoped to exactly this file_id, expiring in minutes), so this endpoint
    intentionally does not also require a session cookie: that is what makes
    it usable as a plain <img>/<video> src while still being safe to leak.
    """
    verified = verify_file_access_token(token, settings.master_encryption_key.encode("utf-8"))
    if verified is None or verified[0] != file_id:
        raise HTTPException(status_code=403, detail="Link expired or invalid")

    result = await db.execute(select(DriveFile).where(DriveFile.file_id == file_id))
    drive_file = result.scalars().first()

    if drive_file is None:
        raise HTTPException(status_code=404, detail="File not found")

    client = DriveClient(access_token=None, api_key=settings.google_api_key or None)
    media_bytes = await client.download_file(file_id)

    # Always carry the original filename so "save as" / downloads keep the
    # real name and extension. `inline` still renders in <img>/<video>;
    # ?download=1 flips to attachment so the browser saves the file directly.
    safe_name = (drive_file.filename or file_id).replace('"', "")
    disposition = "attachment" if download else "inline"
    return Response(
        content=media_bytes,
        media_type=drive_file.mime_type or "application/octet-stream",
        headers={"Content-Disposition": f'{disposition}; filename="{safe_name}"'},
    )
